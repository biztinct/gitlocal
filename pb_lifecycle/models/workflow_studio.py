"""System-wide Studio facade. All business authority stays in existing services."""
import base64
import copy
import hashlib
import json
import logging
import math
import uuid

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError

from . import workflow_definition as D
from .workflow_models import INTERNAL, internal

_logger = logging.getLogger(__name__)
DESIGN = 'pb_lifecycle.group_workflow_designer'
PUBLISH = 'pb_lifecycle.group_workflow_publisher'
TECHNICAL = ('ir.', 'base.', 'mail.', 'bus.', 'web.', 'sms.', 'digest.',
             'res.users', 'res.groups', 'pb.workflow.', 'biz.access', 'biz.approval.')


class WorkflowStudio(models.AbstractModel):
    _name = 'pb.workflow.studio'
    _description = 'Workflow Studio'

    def _staff(self):
        if not self.env.user.has_group('base.group_user'):
            raise AccessError(_('Sign in with an internal account.'))

    def _can_design(self):
        return self.env.su or self.env.user.has_group(DESIGN) or self.env.user.has_group('base.group_system')

    def _design(self):
        self._staff()
        if not self._can_design():
            raise AccessError(_('You can complete your tasks, but cannot edit workflows.'))

    def _publish(self):
        self._design()
        if not (self.env.su or self.env.user.has_group(PUBLISH) or self.env.user.has_group('base.group_system')):
            raise AccessError(_('A workflow publisher must publish or activate this change.'))

    def _company(self, ident=None):
        company = self.env['res.company'].browse(int(ident or self.env.company.id)).exists()
        if not company or company not in self.env.user.company_ids:
            raise AccessError(_('This company is not available to you.'))
        return company

    def _workflow(self, ident, design=True):
        self._design() if design else self._staff()
        rec = self.env['pb.workflow'].sudo().browse(int(ident)).exists()
        if not rec or rec.company_id not in self.env.companies:
            raise AccessError(_('This workflow is not available in your current company.'))
        if not design and not self._can_design() and not ((rec.published_id.starter_group_ids if rec.published_id else rec.starter_group_ids) & self.env.user.group_ids):
            raise AccessError(_('You do not have permission to start this workflow.'))
        return rec

    def _source(self, model, ident):
        if not model or model not in self.env or not int(ident or 0):
            raise UserError(_('Choose a record for this workflow.'))
        rec = self.env[model].browse(int(ident)).exists()
        if not rec:
            raise UserError(_('The source record no longer exists.'))
        rec.check_access('read')
        if 'company_id' not in rec._fields or not rec.company_id or rec.company_id != self.env.company:
            raise AccessError(_('Choose a record from this company.'))
        return rec

    def _source_fields(self, model):
        if not model:
            return [{'key': 'amount', 'label': _('Amount'), 'type': 'float'},
                    {'key': 'urgent', 'label': _('Urgent'), 'type': 'boolean'}]
        obj = self.env[model]
        metadata = obj.fields_get(attributes=['string', 'type', 'selection', 'relation'])
        return [{'key': key, 'label': value['string'], 'type': value['type'],
                 'options': value.get('selection', []), 'relation': value.get('relation')}
                for key, value in metadata.items()
                if key in obj._fields and obj._fields[key].store and
                not key.startswith(('message_', 'activity_')) and
                not any(part in key.lower() for part in ('password', 'token', 'secret', 'api_key', 'credential')) and
                (value['type'] in ('char', 'text', 'integer', 'float', 'monetary', 'boolean', 'date', 'datetime', 'selection') or
                 value['type'] == 'many2one' and value.get('relation') in self.env and
                 self.env[value['relation']].has_access('read'))]

    def _facts(self, record):
        names = [f['key'] for f in self._source_fields(record._name)]
        vals = record.read(names)[0]
        for key, value in list(vals.items()):
            field = record._fields[key]
            if value is False and field.type != 'boolean':
                vals[key] = None
            elif field.type == 'many2one':
                vals[key] = value[0] if value else None
        return vals

    def _models(self):
        rows = []
        for name, model in self.env.registry.models.items():
            if (name.startswith(TECHNICAL) or name in ('res.company', 'pb.workflow') or
                    model._abstract or model._transient or not model._auto or 'company_id' not in model._fields):
                continue
            if not self.env[name].has_access('read'):
                continue
            rows.append({'key': name, 'label': str(model._description or name)})
        # Generic requests are a supported existing business process too.
        if self.env['biz.approval.generic.request'].has_access('read'):
            rows.append({'key': 'biz.approval.generic.request', 'label': _('Other approval request')})
        return sorted(rows, key=lambda x: x['label'].lower())

    def _declared(self, model):
        """The module's own contract (`_workflow_capabilities`), or {}.

        Duck-typed on purpose: the business modules never depend on this
        one. WF2 P2 routes every former per-module special case through it."""
        if model and model in self.env and hasattr(self.env[model], '_workflow_capabilities'):
            return self.env[model]._workflow_capabilities() or {}
        return {}

    def _actions(self, model):
        return dict(self._declared(model).get('actions', {}))

    def _ownership(self, model):
        rows = [{'key': 'approvals', 'label': _('Approval routes, people and backups'),
                 'owner': 'Approval Matrix', 'action': 'pb_approval_config.action_pb_approval_matrix'},
                {'key': 'access', 'label': _('Permissions and access delegation'),
                 'owner': 'Access Studio', 'action': 'biz_access.action_pb_access_board'}]
        declared = self._declared(model).get('owners')
        if declared:
            # The module names its own settings screens; the prefix table
            # below is only the fallback for record types without a contract.
            rows += [dict(r) for r in declared]
            rows.append({'key': 'settings', 'label': _('Existing module settings and templates'),
                         'owner': _('Settings'), 'action': 'pb_settings.action_pb_settings_hub'})
            return [r for r in rows if self.env.ref(r['action'], raise_if_not_found=False)]
        if (model or '').startswith('pb.hiring'):
            rows.append({'key': 'hiring', 'label': _('Stages, candidate messages and automations'),
                         'owner': 'Hiring settings', 'action': 'pb_hiring.action_pb_hiring_hub', 'lens': 'setup'})
        if (model or '').startswith(('pb.journey', 'pb.onboarding', 'pb.offboarding', 'pb.probation', 'pb.pip')) or model == 'hr.employee':
            rows.append({'key': 'journeys', 'label': _('Employee checklists and their automatic work'),
                         'owner': 'Journeys', 'action': 'pb_lifecycle.action_pb_journeys'})
        if (model or '').startswith(('hr.payslip', 'hr.payroll', 'hr.full.final')):
            rows.append({'key': 'pay', 'label': _('Calculation, locks and payment release'),
                         'owner': 'Pay', 'action': 'pb_payhub.action_pb_pay_hub'})
        if (model or '').startswith(('hr.leave', 'pb.clock', 'pb.timesheet')):
            rows.append({'key': 'time', 'label': _('Time policies and attendance rules'),
                         'owner': 'Time', 'action': 'pb_time_hub.action_pb_time_hub'})
        owned = [
            (('pb.expense', 'hr.expense', 'pb.travel'), 'expenses', 'Expenses', 'pb_expenses_hub.action_pb_expenses_hub', 'Expense policies, receipts and payment steps'),
            (('pb.asset', 'maintenance.equipment'), 'assets', 'Assets', 'pb_assets.action_pb_assets', 'Asset custody, returns and handovers'),
            (('pb.learn', 'slide.'), 'learning', 'Learning', 'pb_learning_hub.action_pb_learning_hub', 'Enrolments, learning journeys and course messages'),
            (('hr.integration', 'pb.integration'), 'integrations', 'Integrations', 'pb_integrations.action_pb_integrations', 'Connections, credentials and incoming records'),
            (('hr.attendance', 'pb.attendance'), 'attendance', 'Attendance', 'pb_attendance_flow.action_pb_attendance_flow', 'Clock rules, exceptions and corrections'),
        ]
        for prefixes, key, owner, action, label in owned:
            if (model or '').startswith(prefixes):
                rows.append({'key': key, 'label': _(label), 'owner': _(owner), 'action': action})
        rows.append({'key': 'settings', 'label': _('Existing module settings and templates'),
                     'owner': _('Settings'), 'action': 'pb_settings.action_pb_settings_hub'})
        return [r for r in rows if self.env.ref(r['action'], raise_if_not_found=False)]

    def _studio_rules(self):
        """Automation rules Studio generated for its own workflows (G8).

        They are already listed as workflows, so they never count as
        "existing automation" a designer has to review a second time."""
        return self.env['pb.workflow'].sudo().with_context(active_test=False).search(
            [('automation_id', '!=', False)]).mapped('automation_id')

    def _blocking(self, issues):
        """Errors always block; a "repeats existing" warning blocks until the
        designer keeps the step on purpose (`ack_repeat`)."""
        return [i for i in issues if i.get('severity') != 'warning' or not i.get('acknowledged')]

    @api.model
    def bootstrap(self):
        self._staff()
        company = self._company()
        result = {'company': {'id': company.id, 'name': company.name},
                  'user': {'id': self.env.uid, 'name': self.env.user.name},
                  'can_design': self._can_design(),
                  'can_publish': self.env.user.has_group(PUBLISH) or self.env.user.has_group('base.group_system'),
                  'models': [], 'workflows': [], 'tasks': self.tasks(),
                  'companies': [{'id': c.id, 'name': c.name} for c in self.env.user.company_ids]}
        if self._can_design():
            result.update(models=self._models(), workflows=self.list_workflows())
        else:
            result['workflows'] = [self._row(w) for w in self.env['pb.workflow'].sudo().search([
                ('company_id', '=', company.id), ('enabled', '=', True), ('component', '=', False),
                ('published_id.starter_group_ids', 'in', self.env.user.group_ids.ids)])]
        return result

    def _row(self, w):
        return {'id': w.id, 'name': w.name, 'module': w.module_label or _('Other'),
                'source_model': w.source_model or '', 'revision': w.revision,
                'version': w.published_id.number or 0, 'enabled': w.enabled,
                'component': w.component, 'steps': len((w.draft or {}).get('nodes', [])),
                'trigger': (w.draft or {}).get('trigger', {}).get('kind', 'manual')}

    @api.model
    def list_workflows(self):
        self._design()
        return [self._row(w) for w in self.env['pb.workflow'].sudo().search([
            ('company_id', '=', self._company().id)], limit=500)]

    @api.model
    def create_workflow(self, name, source_model='', module_label='Other', component=False):
        self._design()
        name = str(name or '').strip()[:120]
        if not name:
            raise UserError(_('Give the workflow a name.'))
        if source_model and source_model not in {r['key'] for r in self._models()}:
            raise AccessError(_('This kind of record is not available.'))
        w = internal(self.env['pb.workflow']).create({
            'name': name, 'company_id': self._company().id, 'source_model': source_model,
            'module_label': str(module_label or 'Other')[:80], 'draft': D.fresh(name),
            'execution_user_id': self.env.uid, 'component': bool(component)})
        return self.get_workflow(w.id)

    @api.model
    def get_workflow(self, workflow_id):
        w = self._workflow(workflow_id)
        data = self._row(w)
        data.update(definition=w.draft, process_id=w.process_id.id or None,
                    starter_group_ids=w.starter_group_ids.ids,
                    versions=[{'id': v.id, 'number': v.number, 'date': str(v.published_at),
                               'note': v.note or '', 'by': v.published_by.name} for v in w.version_ids],
                    metadata=self.metadata(w.source_model, workflow_id=w.id),
                    scope_summary=self._scope_summary(w.source_model, (w.draft or {}).get('scope') or {}))
        return data

    @api.model
    def metadata(self, model='', workflow_id=None):
        self._design()
        if model and model not in {r['key'] for r in self._models()}:
            raise AccessError(_('This record type is not available.'))
        company = self._company()
        processes = self.env['biz.approval.process'].sudo().search([('model_name', '=', model)]) if model else self.env['biz.approval.process']
        processes = processes.filtered('connected')
        templates = self.env['mail.template'].search([('model', '=', model or 'pb.workflow.run')], limit=200)
        users = self.env['res.users'].sudo().search([
            ('active', '=', True), ('share', '=', False), ('company_ids', 'in', company.id)], limit=600)
        rules = self.env['base.automation'].sudo().search([
            ('model_id.model', '=', model), ('active', '=', True)]) if model else self.env['base.automation']
        rules -= self._studio_rules()
        result = {'fields': self._source_fields(model), 'actions': self._actions(model),
                  'owners': self._ownership(model),
                  'processes': [{'id': p.id, 'name': p.name, 'key': p.key} for p in processes],
                  'templates': [{'id': t.id, 'name': t.name} for t in templates],
                  'can_edit_templates': self.env['mail.template'].has_access('create') and
                                        (self.env.is_admin() or self.env.user.has_group('mail.group_mail_template_editor')),
                  'activity_types': [{'id': t.id, 'name': t.name} for t in self.env['mail.activity.type'].search([
                      ('res_model', 'in', [False, 'pb.workflow.run']), ('category', '=', 'default')])],
                  'users': [{'id': u.id, 'name': u.name} for u in users],
                  'roles': [{'id': r.id, 'name': r.name} for r in self.env['biz.approval.role'].sudo().search([('is_pool', '=', False)])],
                  'starter_groups': [{'id': g.id, 'name': g.name} for g in self.env['res.groups'].sudo().search([('id', '!=', self.env.ref('base.group_public').id), ('id', '!=', self.env.ref('base.group_portal').id)])],
                  'automations': [{'id': a.id, 'name': a.name, 'trigger': a.trigger} for a in rules],
                  'components': [self._row(c) for c in self.env['pb.workflow'].sudo().search([
                      ('company_id', '=', company.id), ('component', '=', True), ('published_id', '!=', False)])]}
        # Kept for screens cached before WF2 P2: the module action's stage
        # choices, now read from the module's contract.
        for spec in result['actions'].values():
            for param in spec.get('params', []):
                if param.get('key') == 'stage_key' and param.get('type') == 'choice':
                    result['stages'] = list(param.get('options', []))
        return result

    def _validate(self, w, definition):
        fields_meta = {f['key']: f for f in self._source_fields(w.source_model)}
        after = isinstance(definition, dict) and isinstance(definition.get('trigger'), dict) and definition['trigger'].get('kind') == 'approval_applied'
        errors = D.validate(definition, fields_meta, self._actions(w.source_model))
        if errors:
            return errors
        def error(key, code, text):
            errors.append({'id': key, 'code': code, 'text': text, 'severity': 'error'})
        trigger = definition['trigger']
        matrix = [n for n in definition['nodes'] if n['type'] == 'matrix']
        # An approval step is optional (R2): the record's own module keeps its
        # approval. A process is needed only when this workflow refers to one.
        if w.source_model and matrix and not w.process_id:
            error('trigger', 'approval_process_missing', _('Choose the existing approval process for this record.'))
        if not w.source_model and any(n.get('mode') == 'follow' for n in matrix):
            error(matrix[0]['id'], 'follow_needs_record', _('A new process has no record of its own to follow. Choose “Send it for approval”.'))
        if trigger['kind'] not in ('manual', 'schedule') and not w.source_model:
            error('trigger', 'automatic_needs_record', _('Choose an existing record for an automatic start.'))
        if trigger['kind'] == 'approval_applied' and not w.process_id:
            error('trigger', 'trigger_process_missing', _('Choose the approval process this follows.'))
        if after and matrix:
            error('trigger', 'approval_already_done', _('Approval is already complete for this trigger. Do not request it again.'))
        if trigger['kind'] == 'date':
            f = fields_meta.get(trigger.get('date_field'), {})
            if f.get('type') not in ('date', 'datetime'):
                error('trigger', 'date_field', _('Choose a date field.'))
            if type(trigger.get('delay', 0)) is not int or not 0 <= trigger.get('delay', 0) <= 365:
                error('trigger', 'date_delay', _('Use a delay from 0 to 365.'))
            if trigger.get('unit') not in ('minutes', 'hour', 'day', 'month') or trigger.get('mode', 'after') not in ('before', 'after'):
                error('trigger', 'date_offset', _('Choose a valid date offset.'))
        bindings = set()
        actions = self._actions(w.source_model)
        for n in definition['nodes']:
            if n['type'] == 'input':
                for field in n['form']['fields']:
                    if field.get('type') == 'lookup' and field.get('lookup_model') not in {r['key'] for r in self._models()}:
                        error(n['id'], 'lookup_model', _('Choose an accessible record type for the lookup.'))
                    if field.get('bind'):
                        if field['bind'] in bindings:
                            error(n['id'], 'duplicate_binding', _('Map each approval value from one form field only.'))
                        bindings.add(field['bind'])
            if n['type'] in D.PEOPLE + ('notify',) and n.get('owner', {}).get('kind') == 'role':
                role = self.env['biz.approval.role'].sudo().browse(n['owner'].get('id', 0)).exists()
                if not role or role.is_pool:
                    error(n['id'], 'bad_role', _('Choose an existing single-person responsibility.'))
            if n['type'] in D.PEOPLE + ('notify',):
                if n.get('owner', {}).get('kind') in ('manager', 'managers_manager') and not w.source_model:
                    error(n['id'], 'owner_needs_record', _('A new process has no record that names a manager. Choose someone else.'))
                if n.get('owner', {}).get('kind') == 'field':
                    f = fields_meta.get(n['owner'].get('field'), {})
                    if f.get('type') != 'many2one' or f.get('relation') != 'res.users':
                        error(n['id'], 'bad_owner_field', _('Choose a person field from this record.'))
                if n.get('activity_type_id') and n['activity_type_id'] not in self._activity_types().ids:
                    error(n['id'], 'bad_task_type', _('Choose a supported task type.'))
                if n.get('owner', {}).get('kind') == 'subject' and not (
                        w.source_model and hasattr(self.env[w.source_model], '_workflow_subject')):
                    error(n['id'], 'subject_not_available', _('This kind of record does not say who it is about. Choose someone else.'))
            if n['type'] == 'email':
                try:
                    self._mail_template(n['template_id'], w.source_model or 'pb.workflow.run')
                except (AccessError, UserError) as exc:
                    error(n['id'], 'email_template', str(exc))
                # The same template twice is checked per path (WF2 P2,
                # `workflow_contract._validate`): exclusive branches may each
                # send it.
                if not n.get('purpose', '').strip():
                    error(n['id'], 'email_purpose', _('Say why this message is additional to existing notifications.'))
            if n['type'] in D.PEOPLE + ('notify',) and n.get('owner', {}).get('kind') == 'user':
                user = self.env['res.users'].sudo().browse(n['owner']['id']).exists()
                if not user or not user.active or user.share or w.company_id not in user.company_ids:
                    error(n['id'], 'inactive_owner', _('Choose an active person in this company.'))
            if n['type'] == 'action' and n.get('action_key') in actions:
                # Choices the module declares for its own operation (e.g.
                # which Hiring stage). Read from the node itself or from
                # `parameters`, so versions saved before the contract work.
                values = self._action_params(n, actions[n['action_key']])
                for param in actions[n['action_key']].get('params', []):
                    # Choice keys are compared as text: a screen sends them so.
                    if param.get('type') == 'choice' and str(values.get(param['key'])) not in {
                            str(o['key']) for o in param.get('options', [])}:
                        error(n['id'], param.get('code') or 'bad_action_choice',
                              param.get('error') or _('Choose one of the listed options for “%s”.', param.get('label', '')))
            if n['type'] == 'reference' and n.get('owner_key') not in {r['key'] for r in self._ownership(w.source_model)}:
                error(n['id'], 'bad_reference_owner', _('Choose an existing owner from the list.'))
            for code, text in self._new_step_issues(w, definition, n):
                error(n['id'], code, text)
        return errors

    def _new_step_issues(self, w, d, n):
        """Checks of the WF2 P3b step types that need the database: the
        stage, value, template or workflow a step names must exist, belong
        here and be allowed. Codes, never wording (ledger G2)."""
        kind, company, model = n['type'], w.company_id, w.source_model or ''
        out = []
        if kind == 'stage_move':
            contract = self._contract(model) if model else {}
            if contract.get('own_stage_rows'):
                return [('stage_move_area', _('%(label)s stages belong to %(area)s. Use “Move to a Hiring stage” instead.',
                                               label=contract['label'], area=contract['area']))]
            stage = self.env['pb.workflow.stage'].sudo().browse(int((n.get('target') or {}).get('id') or 0)).exists()
            if not stage or not stage.active or stage.company_id != company or (
                    (stage.source_model or '') != model or (not model and stage.workflow_id != w)):
                out.append(('stage_move_target', _('Choose one of your stages to move it to.')))
        if kind == 'update':
            if not model:
                return [('update_needs_record', _('A new process has no record to update.'))]
            contract = self._contract(model)
            safe = contract.get('safe_fields') or []
            if not safe:
                return [('update_not_open', _('%s has not opened any values to workflows yet.', contract['area']))]
            spec = self._safe_spec(model, n.get('field'))
            if not spec and n.get('field') in contract.get('retired_fields', []):
                # WF2 P4a (D14): e.g. Hiring's evaluation stars.
                return [('update_field', _('%s no longer offers this value. Choose another.', contract['area']))]
            if not spec or n.get('field') == contract.get('stage_field'):
                return [('update_field', _('Choose one of the values %s lets workflows set.', contract['area']))]
            if n.get('value_from'):
                source_kind = self._answer_kind(d, n['value_from'])
                if source_kind not in D.FEEDS.get(spec.get('type'), ()):
                    out.append(('update_value_from', _('That answer is not %(kind)s, so it cannot fill “%(label)s”.',
                                                       kind=_(D.TYPE_WORDS.get(spec.get('type'), 'a value')),
                                                       label=spec.get('label'))))
            elif spec.get('type') == 'text' and not str(n.get('value') or '').strip():
                out.append(('update_value', _('Write what to set “%s” to.', spec.get('label'))))
            else:
                try:
                    self._safe_value(spec, n.get('value'), company)
                except UserError as exc:
                    out.append(('update_value', str(exc)))
        if kind == 'create':
            creator = self._creator(n.get('creator'))
            if not creator:
                return out
            if not creator['available']:
                return [('create_unavailable', _('This app is not switched on here.'))]
            if creator['needs_subject'] and not (model and hasattr(self.env[model], '_workflow_subject')):
                return [('create_needs_subject', _('Letters are written for the person a record is about, and this kind of record does not say who that is.'))]
            template = self.env[creator['template_model']].sudo().browse(int(n.get('template_id') or 0)).exists()
            if not template or template not in self._creator_templates(creator, company, readable=False):
                out.append(('create_template', _('Choose the template to start from.')))
        if kind == 'start':
            target = self.env['pb.workflow'].sudo().browse(int(n.get('workflow_id') or 0)).exists()
            if not target or target.company_id != company:
                out.append(('start_target', _('Choose the workflow to hand over to.')))
            elif target == w:
                out.append(('start_self', _('A workflow cannot start itself. Choose another one.')))
            elif (target.source_model or '') != model or target.component:
                out.append(('start_target', _('“%s” is for another kind of record. Choose one for the same records.', target.name)))
            elif not target.published_id:
                out.append(('start_unpublished', _('Publish “%s” first, so there is a version to start.', target.name)))
            elif target.published_id.definition['trigger']['kind'] != 'manual':
                out.append(('start_automatic', _('“%s” starts by itself, so it cannot be handed over to. Choose one that a person starts.', target.name)))
        return out

    def _answer_kind(self, d, key):
        """The kind of an earlier answer `step.<id>.<field>`: the form
        field's type, or `outcome` for a person step's chosen button."""
        parts = str(key).split('.')
        if len(parts) != 3 or parts[0] != 'step':
            return None
        node = next((x for x in d['nodes'] if x['id'] == parts[1]), None)
        if not node:
            return None
        if parts[2] == 'outcome':
            return 'outcome'
        field = next((f for f in (node.get('form') or {}).get('fields', []) if f.get('id') == parts[2]), None)
        return field.get('type') if field else None

    @api.model
    def save_draft(self, workflow_id, revision, definition, process_id=None, execution_user_id=None, starter_group_ids=None):
        # `execution_user_id` is still accepted from older screens and ignored:
        # workflows run at system level (R3), never as a chosen person.
        w = self._workflow(workflow_id)
        w._lock()
        if type(revision) is not int or revision != w.revision:
            raise UserError(_('Someone saved a newer draft. Reload before applying your changes.'))
        if not isinstance(definition, dict) or not D.safe_json(definition):
            raise UserError(_('This workflow is too large.'))
        # Every saved draft decides paths on the record as it is when the path
        # is reached. Published versions keep whatever they were saved with.
        definition = dict(definition, timing='live')
        structural = D.validate(definition, {f['key'] for f in self._source_fields(w.source_model)}, self._actions(w.source_model))
        # Drafts may be unfinished, but never structurally corrupt. Decided by
        # code, never by wording (ledger G2).
        blocking = [i for i in structural if i.get('code') in D.STRUCTURAL]
        if blocking:
            raise UserError('\n'.join(i['text'] for i in blocking))
        vals = {'draft': definition, 'name': str(definition.get('name', '')).strip()[:120] or w.name,
                'revision': w.revision+1}
        if starter_group_ids is not None:
            self._publish()
            if not isinstance(starter_group_ids, list) or any(type(i) is not int for i in starter_group_ids):
                raise UserError(_('Choose who can start this workflow.'))
            groups = self.env['res.groups'].sudo().browse(starter_group_ids).exists()
            if len(groups) != len(set(starter_group_ids)):
                raise UserError(_('A selected role no longer exists.'))
            vals['starter_group_ids'] = [(6, 0, groups.ids)]
        if process_id:
            p = self.env['biz.approval.process'].sudo().browse(int(process_id)).exists()
            if not p or p.model_name != w.source_model or not p.connected:
                raise UserError(_('Choose an approval process belonging to this record.'))
            vals['process_id'] = p.id
        internal(w).write(vals)
        # The "When …" sentence on the workbench reads the same plain filter
        # words Review uses (one describer, WF2 P3a).
        return {'revision': w.revision, 'issues': self._validate(w, definition),
                'scope_summary': self._scope_summary(w.source_model, definition.get('scope') or {})}

    TRIGGER_LABELS = {'manual': 'Started by a person', 'created': 'When a record is created',
                      'changed': 'When selected fields change', 'date': 'Based on a record date',
                      'approval_applied': 'After approval is applied'}
    OP_WORDS = {'eq': 'is', 'ne': 'is not', 'gt': 'is more than', 'gte': 'is at least',
                'lt': 'is less than', 'lte': 'is at most', 'contains': 'contains',
                'icontains': 'contains', 'not_contains': 'does not contain',
                'set': 'is filled in', 'unset': 'is empty', 'in': 'is one of', 'not_in': 'is not one of'}

    def _scope_summary(self, model, scope):
        """A short plain sentence naming which records a workflow starts for."""
        words = self._rule_words(model, scope)
        return _('Records where %s', words) if words else _('Every record')

    def _rule_words(self, model, scope):
        """The filters of a rule in words ("Urgent is Yes and …"), or ''."""
        rules = D.leaves(scope) if isinstance(scope, dict) and scope.get('rules') else []
        # A rule still being written (no value yet) is left out, so the
        # words never say "ID is" (WF2 P3b).
        rules = [r for r in rules if r.get('op') in ('set', 'unset') or r.get('value') not in (None, '', [])]
        if not rules:
            return ''
        meta = {f['key']: f for f in self._source_fields(model)}
        def value(rule):
            f, v = meta.get(rule.get('field'), {}), rule.get('value')
            values = v if isinstance(v, list) else [v]
            if f.get('type') == 'selection':
                labels = dict(f.get('options') or [])
                values = [labels.get(x, x) for x in values]
            elif f.get('type') == 'many2one' and f.get('relation') in self.env:
                found = self.env[f['relation']].browse([x for x in values if type(x) is int]).exists()
                values = [r.display_name for r in found] or values
            elif f.get('type') == 'boolean':
                values = [_('Yes') if x else _('No') for x in values]
            return ', '.join(str(x) for x in values)
        parts = []
        for rule in rules[:2]:
            label = meta.get(rule.get('field'), {}).get('label') or _('a value')
            words = _(self.OP_WORDS.get(rule.get('op'), 'is'))
            parts.append('%s %s' % (label, words) if rule.get('op') in ('set', 'unset') else '%s %s %s' % (label, words, value(rule)))
        joiner = _(' and ') if scope.get('match') == 'all' else _(' or ')
        text = joiner.join(parts)
        if len(rules) > 2:
            text = _('%(text)s, plus %(count)s more filters', text=text, count=len(rules) - 2)
        return text

    def _other_row(self, w):
        row = self._row(w)
        d = w.published_id.definition if w.published_id else (w.draft or {})
        kind = (d.get('trigger') or {}).get('kind', 'manual')
        row.update(trigger=kind, trigger_label=_(self.TRIGGER_LABELS.get(kind, 'Started by a person')),
                   scope_summary=self._scope_summary(w.source_model, d.get('scope') or {}))
        return row

    @api.model
    def review(self, workflow_id):
        w = self._workflow(workflow_id)
        issues = self._validate(w, w.draft)
        others = self.env['pb.workflow'].sudo().search([
            ('company_id', '=', w.company_id.id), ('source_model', '=', w.source_model),
            ('enabled', '=', True), ('id', '!=', w.id)])
        return {'issues': issues, 'blocking': len(self._blocking(issues)),
                'other_workflows': [self._other_row(x) for x in others],
                'automations': self.metadata(w.source_model, w.id)['automations'],
                'impact': _('Existing runs keep their version. Publishing does not activate this workflow.'),
                'changed': w.published_id.definition != w.draft if w.published_id else True}

    @api.model
    def publish(self, workflow_id, revision, note=''):
        self._publish()
        w = self._workflow(workflow_id)
        w._lock()
        if w.revision != revision:
            raise UserError(_('Reload the latest draft before publishing.'))
        issues = self._blocking(self._validate(w, w.draft))
        if issues:
            raise UserError('\n'.join(i['text'] for i in issues))
        if not w.source_model and any(n['type'] == 'matrix' for n in w.draft['nodes']) and not w.process_id:
            p = self.env['biz.approval.process'].sudo().create({
                'key': 'workflow_%s' % w.id, 'name': w.name,
                'model_name': 'pb.workflow.run', 'area': 'other',
                'description': _('Approval route for this custom Workflow Studio process.')})
            internal(w).write({'process_id': p.id})
        version = internal(self.env['pb.workflow.version']).create({
            'workflow_id': w.id, 'number': max(w.version_ids.mapped('number') or [0])+1,
            'definition': copy.deepcopy(w.draft), 'process_id': w.process_id.id,
            'execution_user_id': w.execution_user_id.id,
            'starter_group_ids': [(6, 0, w.starter_group_ids.ids)],
            'published_by': self.env.uid, 'note': str(note)[:240]})
        # A newly published definition is reviewed before automatic activation.
        internal(w).write({'published_id': version.id, 'enabled': False})
        w._sync_automation()
        return self.get_workflow(w.id)

    @api.model
    def activate(self, workflow_id, enabled, acknowledge_existing=False):
        self._publish()
        w = self._workflow(workflow_id)
        w._lock()
        if enabled:
            if not w.published_id or w.component:
                raise UserError(_('Publish a process before activating it.'))
            issues = self._blocking(self._validate(w, w.published_id.definition))
            if issues:
                raise UserError('\n'.join(i['text'] for i in issues))
            definition = w.published_id.definition
            kind = definition['trigger']['kind']
            if kind != 'manual':
                # Several workflows may start for the same kind of record
                # (F2). Only an exact copy is refused; any other overlap is a
                # deliberate choice the publisher confirms on Review.
                peers = self.env['pb.workflow'].sudo().search([
                    ('company_id', '=', w.company_id.id), ('source_model', '=', w.source_model),
                    ('enabled', '=', True), ('id', '!=', w.id), ('published_id', '!=', False)])
                canon = lambda value: json.dumps(value or {}, sort_keys=True)
                same_kind = peers.filtered(lambda p: p.published_id.definition['trigger']['kind'] == kind)
                if any(canon(p.published_id.definition['trigger']) == canon(definition['trigger']) and
                       canon(p.published_id.definition.get('scope')) == canon(definition.get('scope'))
                       for p in same_kind):
                    raise UserError(_('Another active workflow starts on exactly the same records and event. Change the filters or pause the other one.'))
                if same_kind and not acknowledge_existing:
                    raise UserError(_('Other workflows also start for these records. Review them and confirm this one does different work.'))
                existing = self.metadata(w.source_model, w.id)['automations']
                if existing and not acknowledge_existing:
                    raise UserError(_('Review existing automation rules and confirm that this workflow has a different purpose.'))
            if not w.source_model and any(n['type'] == 'matrix' for n in definition['nodes']):
                # A new process sends its own approvals, so its route must
                # exist first. Resolution is the engine's, never re-implemented.
                found = self.env['biz.approval.engine'].resolve_binding(
                    w.company_id.id, w.process_id.key, [''], 'any') if w.process_id else {'error': {'code': 'no_route'}}
                problem = found.get('error') or {}
                if problem.get('code') in ('no_route', 'no_version'):
                    raise UserError(_('Set up who approves this in Approval Matrix before turning it on.'))
                if problem.get('code') == 'paused':
                    # WF2 P2 (P1 deviation 3 reversed by the handover): a new
                    # process cannot start while its own route is paused.
                    raise UserError(_('The approval route for this is paused. Switch it back on in Approval Matrix first.'))
                if problem.get('code') == 'ambiguous_route':
                    raise UserError(problem['message'])
            if kind == 'approval_applied':
                last = self.env['biz.approval.event'].sudo().search([], order='id desc', limit=1)
                internal(w).write({'last_approval_event_id': last.id or 0})
        internal(w).write({'enabled': bool(enabled)})
        w._sync_automation()
        return self.get_workflow(w.id)

    @api.model
    def restore(self, workflow_id, version_id, revision):
        w = self._workflow(workflow_id)
        version = w.version_ids.filtered(lambda v: v.id == int(version_id))
        if not version:
            raise UserError(_('This version belongs to another workflow.'))
        return self.save_draft(w.id, revision, version.definition)

    @api.model
    def component(self, workflow_id):
        w = self._workflow(workflow_id)
        if not w.component or not w.published_id:
            raise UserError(_('Choose a published saved group.'))
        return {'name': w.name, 'version': w.published_id.number,
                'definition': w.published_id.definition}

    @api.model
    def preview(self, workflow_id, values=None, before_values=None):
        w = self._workflow(workflow_id)
        issues = self._blocking(self._validate(w, w.draft))
        if issues:
            return {'issues': issues, 'steps': []}
        values = values or {}
        if not isinstance(values, dict) or len(json.dumps(values)) > 100000:
            raise UserError(_('The example values are not valid.'))
        included = D.matches(w.draft['scope'], values)
        if w.draft['trigger'].get('before'):
            if not isinstance(before_values, dict) or not D.safe_json(before_values, 100000):
                return {'issues': [{'id': 'trigger', 'code': 'preview_needs_before', 'text': _('Add example values from before the change.')}], 'steps': []}
            included = included and D.matches(w.draft['trigger']['before'], before_values)
        return {'issues': [], 'included': included,
                'steps': D.route_preview(w.draft, values, self._would(w)) if included else [],
                'notice': _('Preview only. No tasks, approvals or messages are created.')}

    @api.model
    def search_records(self, workflow_id, term=''):
        w = self._workflow(workflow_id, design=False)
        if not w.source_model:
            return []
        records = self.env[w.source_model].search([
            ('company_id', '=', w.company_id.id), ('display_name', 'ilike', str(term)[:100])], limit=30)
        return [{'id': r.id, 'name': r.display_name} for r in records]

    def _enqueue(self, w, source_id, initiator, key, initial=None, request_id=None):
        Event = internal(self.env['pb.workflow.event'])
        self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', [key])
        old = Event.search([('key', '=', key)], limit=1)
        if old:
            return old
        if source_id:
            self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ['workflow-record:%s:%s' % (w.id, source_id)])
            active = Event.search([('workflow_id', '=', w.id), ('company_id', '=', w.company_id.id), ('source_id', '=', source_id),
                '|', ('state', '=', 'pending'), ('run_id.state', 'in', ['running', 'waiting', 'failed', 'held'])], limit=1)
            if active:
                return active
        return Event.create({'workflow_id': w.id, 'version_id': w.published_id.id,
            'company_id': w.company_id.id, 'source_model': w.source_model,
            'source_id': source_id or 0, 'initiator_id': initiator,
            'execution_user_id': (w.published_id.execution_user_id or w.execution_user_id).id, 'key': key,
            'initial_values': initial or {}, 'approval_request_id': request_id or False})

    @api.model
    def start(self, workflow_id, source_id=None, token=None, initial=None):
        w = self._workflow(workflow_id, design=False)
        if not w.enabled or not w.published_id or w.component:
            raise UserError(_('This workflow is not active.'))
        if w.published_id.definition['trigger']['kind'] != 'manual':
            raise UserError(_('This workflow starts from its configured event.'))
        try:
            token = str(uuid.UUID(str(token)))
        except (ValueError, TypeError, AttributeError):
            raise UserError(_('Reload the start dialog and try again.'))
        if w.source_model:
            self._source(w.source_model, source_id).check_access('write')
        key = 'manual:%s:%s:%s' % (w.id, self.env.uid, token)
        initial = initial or {}
        if (not isinstance(initial, dict) or set(initial) - {'amount', 'urgent'} or
                type(initial.get('amount', 0)) not in (int, float) or not math.isfinite(initial.get('amount', 0)) or type(initial.get('urgent', False)) is not bool):
            raise UserError(_('Enter a valid amount and urgency.'))
        event = self._enqueue(w, source_id, self.env.uid, key, initial)
        event._process()
        return {'event_id': event.id, 'run_id': event.run_id.id or None,
                'state': event.state, 'error': event.error or ''}

    def _capture(self, workflow_id, records):
        """Fixed generated server-action entry. Private: never callable by RPC."""
        w = self.env['pb.workflow'].sudo().browse(int(workflow_id)).exists()
        if self.env.context.get('_pb_workflow_internal') is INTERNAL and self.env.context.get('_pb_workflow_origin') == w.id:
            return
        if not w or not w.enabled or records._name != w.source_model:
            return
        for rec in records:
            if rec.company_id != w.company_id:
                continue
            t = w.published_id.definition['trigger']
            stamp = str(rec.write_date or rec.create_date or '')
            selected = {k: str(rec[k]) for k in t.get('fields', []) if k in rec._fields}
            digest = hashlib.sha256(json.dumps([stamp, selected], sort_keys=True).encode()).hexdigest()
            key = 'native:%s:%s:%s:%s' % (w.id, w.published_id.id, rec.id, digest)
            self._enqueue(w, rec.id, self._capture_initiator(w, rec), key)

    def _capture_initiator(self, w, rec):
        """Who a system-triggered start is recorded as (WF2 P2, F10).

        A date rule or a background job runs as the system account. When the
        record's module says who the record is about and that person has an
        active staff login in the workflow's company, the run is theirs;
        otherwise it stays the system's, as before."""
        if self.env.uid != SUPERUSER_ID or not hasattr(rec, '_workflow_subject'):
            return self.env.uid
        try:
            user = (rec.sudo()._workflow_subject() or {}).get('user')
        except (AccessError, UserError):
            return self.env.uid
        user = user.sudo().exists() if user else None
        if user and len(user) == 1 and user.active and not user.share and w.company_id in user.company_ids:
            return user.id
        return self.env.uid

    def _mail_template(self, ident, model):
        template = self.env['mail.template'].browse(int(ident)).exists()
        if not template:
            raise UserError(_('This email template no longer exists.'))
        template.check_access('read')
        if template.model != model:
            raise UserError(_('Choose a template for this kind of record.'))
        if 'company_id' in template._fields and template.company_id and template.company_id != self.env.company:
            raise AccessError(_('This template belongs to another company.'))
        return template

    def _execute_action(self, source, node):
        # Under system execution this check always passes; the guard below and
        # the module's own facade decide whether the action may happen.
        source.check_access('write')
        key = node['action_key']
        actions = self._actions(source._name)
        if key not in actions:
            raise UserError(_('This business action is no longer available.'))
        # The module's own operation and safeguards decide (WF2 P2): Studio
        # no longer knows any module's verbs (Hiring's stage move included).
        if hasattr(source, '_workflow_execute'):
            return source._workflow_execute(key, self._action_params(node, actions[key]))
        raise UserError(_('The module has not registered this action.'))

    def _action_params(self, node, spec):
        """A module action's parameters: from `parameters`, else from the node
        itself (where versions saved before the contract keep them)."""
        given = node.get('parameters') if isinstance(node.get('parameters'), dict) else {}
        return {p['key']: given.get(p['key'], node.get(p['key'])) for p in spec.get('params', []) if p.get('key')}

    def _run(self, ident):
        self._staff()
        run = self.env['pb.workflow.run'].browse(int(ident)).exists()
        if not run:
            raise UserError(_('This run no longer exists.'))
        run.check_access('read')
        if run.company_id not in self.env.companies:
            raise AccessError(_('This run belongs to another company.'))
        if run.source_model:
            self._source(run.source_model, run.source_id)
        return run

    def _readable_run(self, run):
        try:
            self._run(run.id)
            return True
        except (AccessError, UserError):
            return False

    @api.model
    def runs(self, workflow_id=None):
        self._progress_permission()
        domain = [('company_id', '=', self._company().id)]
        if workflow_id:
            domain.append(('workflow_id', '=', int(workflow_id)))
        return [{'id': r.id, 'name': r.name, 'state': r.state,
                 'version': r.sudo().version_id.number, 'started': str(r.create_date),
                 'initiator': r.initiator_id.name} for r in self.env['pb.workflow.run'].search(domain, limit=100) if self._readable_run(r)]

    @api.model
    def run_detail(self, run_id):
        run = self._run(run_id)
        can_manage = self._can_design()
        if not can_manage:
            return {'id': run.id, 'name': run.name, 'state': run.state, 'tasks': self.tasks(run_id=run.id)}
        srun = run.sudo()
        return {'id': run.id, 'name': run.name, 'state': run.state,
                'steps': [{'id': s.id, 'key': s.key, 'name': s.name, 'state': s.state,
                           'kind': s.kind, 'owner': s.assignee_id.name or '',
                           'error': s.error or '', 'approval_id': s.approval_id.id or None,
                           'wake_at': str(s.wake_at) if s.wake_at else ''} for s in srun.step_ids],
                'history': [{'text': l.message, 'at': str(l.create_date), 'by': l.actor_id.name} for l in srun.log_ids],
                'tasks': self.tasks(run_id=run.id)}

    @api.model
    def tasks(self, run_id=None):
        self._staff()
        domain = [('assignee_id', '=', self.env.uid), ('state', '=', 'waiting'),
                  ('kind', 'in', list(D.PEOPLE)), ('company_id', '=', self._company().id),
                  ('run_id.state', 'not in', ['held', 'cancelled', 'rejected', 'done'])]
        if run_id:
            domain.append(('run_id', '=', int(run_id)))
        return [{'id': s.id, 'name': s.name, 'workflow': s.run_id.name,
                 'run_id': s.run_id.id, 'kind': s.kind,
                 'due': str(s.activity_id.date_deadline) if s.activity_id else ''}
                for s in self.env['pb.workflow.step'].search(domain, limit=200) if self._readable_run(s.run_id)]

    def _task(self, task_id):
        self._staff()
        task = self.env['pb.workflow.step'].browse(int(task_id)).exists()
        if not task:
            raise UserError(_('This task no longer exists.'))
        task.check_access('read')
        if task.assignee_id.id != self.env.uid or task.company_id not in self.env.companies:
            raise AccessError(_('Only the assigned person can complete this task.'))
        self._run(task.run_id.id)
        if task.run_id.state in ('held', 'done', 'cancelled', 'rejected') or task.state != 'waiting':
            raise UserError(_('This task is not waiting for an answer.'))
        return task.sudo()

    def _prefills(self, task):
        form = task.config.get('form', {})
        run = task.run_id
        values = self._facts(self._source(run.source_model, run.source_id)) if run.source_model else run.facts or {}
        return {f['id']: values.get(f['prefill']) for f in form.get('fields', []) if f.get('prefill')}

    @api.model
    def task_detail(self, task_id):
        task = self._task(task_id)
        form = task.config.get('form', {'fields': []})
        prefills = self._prefills(task)
        answers = {k: v for k, v in (task.answers or {}).items() if not str(k).startswith('_')}
        back = (task.answers or {}).get('_sent_back') or None
        return {'id': task.id, 'name': task.name, 'workflow': task.run_id.name,
                # WF2 P3b: the buttons that finish it, what a confirmation
                # asks the person to read, and the note it came back with.
                'buttons': D.buttons(task.config) if task.kind in ('task', 'confirm') else [],
                'text': task.config.get('text', '') if task.kind == 'confirm' else '',
                'sent_back': back,
                'form': form, 'answers': {**answers, **prefills},
                'readonly': list(prefills), 'instructions': task.config.get('notes', ''),
                'file_names': {a.id: a.name for a in self.env['ir.attachment'].search([('res_model', '=', 'pb.workflow.step'), ('res_id', '=', task.id), ('create_uid', '=', self.env.uid)])},
                'lookup_names': {f['id']: self._source(f['lookup_model'], task.answers[f['id']]).display_name for f in form.get('fields', []) if f['type'] == 'lookup' and (task.answers or {}).get(f['id'])},
                'kind': task.kind}

    @api.model
    def answer(self, task_id, values=None, complete=True):
        task = self._task(task_id)
        run = task.run_id
        run._lock()
        # Re-read after locking; another tab may just have completed it.
        if task.state != 'waiting':
            raise UserError(_('This step has already been completed.'))
        cleaned, errors = D.validate_answers(task.config.get('form', {'fields': []}), values or {},
                                             self._prefills(task), partial=not complete) if task.kind == 'input' else ({}, {})
        if task.kind in ('task', 'confirm'):
            # The chosen button (required when there are several) and an
            # optional note (WF2 P3b).
            cleaned, errors = D.validate_outcome(task.config, values or {}) if complete else ({}, {})
        if errors:
            return {'ok': False, 'errors': errors}
        if not complete and (task.answers or {}).get('_sent_back'):
            cleaned = dict(cleaned, _sent_back=task.answers['_sent_back'])
        for f in task.config.get('form', {}).get('fields', []):
            if f['type'] == 'lookup' and cleaned.get(f['id']):
                self._source(f['lookup_model'], cleaned[f['id']])
            if f['type'] == 'file':
                for ident in cleaned.get(f['id'], []):
                    att = self.env['ir.attachment'].browse(ident).exists()
                    if not att or att.res_model != 'pb.workflow.step' or att.res_id != task.id or att.create_uid.id != self.env.uid:
                        raise AccessError(_('Use files uploaded for this task.'))
                    att.check_access('read')
        internal(task).write({'answers': cleaned})
        if complete:
            task._finish(cleaned)
            if task.kind == 'confirm':
                run._log(_('%(who)s confirmed: “%(what)s”.', who=self.env.user.name, what=cleaned.get('outcome_label', '')), task)
            elif len(D.buttons(task.config)) > 1:
                run._log(_('%(who)s chose “%(what)s”.', who=self.env.user.name, what=cleaned.get('outcome_label', '')), task)
            run._advance()
        return {'ok': True, 'complete': bool(complete), 'run_id': run.id}

    @api.model
    def upload(self, task_id, name, content, mimetype='application/octet-stream'):
        task = self._task(task_id)
        try:
            raw = base64.b64decode(content, validate=True)
        except (ValueError, TypeError):
            raise UserError(_('This file could not be read.'))
        if not raw or len(raw) > 10 * 1024 * 1024:
            raise UserError(_('Choose a file up to 10 MB.'))
        # Persist through the existing attachment ACL; no public/token access.
        att = self.env['ir.attachment'].create({'name': str(name)[:180], 'datas': content,
                'mimetype': str(mimetype)[:100], 'res_model': 'pb.workflow.step',
                'res_id': task.id, 'company_id': task.company_id.id, 'public': False})
        return {'id': att.id, 'name': att.name}

    @api.model
    def run_action(self, run_id, action, step_id=None):
        self._design()
        run = self._run(run_id).sudo()
        run._lock()
        if action == 'hold' and run.state in ('running', 'waiting', 'failed'):
            internal(run).write({'state': 'held'})
        elif action == 'resume' and run.state == 'held':
            internal(run).write({'state': 'waiting'})
            run._advance()
        elif action == 'retry':
            step = run.step_ids.filtered(lambda s: s.id == int(step_id or 0) and s.state == 'failed')
            if not step or run.state == 'held':
                raise UserError(_('Choose a failed step in an active run.'))
            if step.kind == 'send_back' and str(step.choice or '').isdigit() and int(step.choice) >= D.SEND_BACK_LIMIT:
                # Someone looked at it: carry on without a fourth send back.
                step._finish()
                internal(step).write({'error': _('Carried on without sending it back again.')})
                run._log(_('Carried on without sending it back again.'), step)
                internal(run).write({'state': 'running'})
                run._advance()
                run._log(_('%s by %s.', action.capitalize(), self.env.user.name))
                return self.run_detail(run.id)
            if step.attempts >= 5:
                raise UserError(_('This step has failed five times. Resolve the source issue before starting a new run.'))
            internal(step).write({'state': 'pending', 'error': False})
            run._advance()
        elif action == 'cancel' and run.state not in ('done', 'cancelled', 'rejected'):
            if run.step_ids.mapped('approval_id').filtered(lambda r: r.state in ('pending', 'blocked', 'approved')):
                raise UserError(_('Withdraw the pending request in Approvals before cancelling this run.'))
            for step in run.step_ids:
                step._cancel_activity()
            internal(run).write({'state': 'cancelled', 'ended_at': fields.Datetime.now()})
        else:
            raise UserError(_('This action is not available now.'))
        run._log(_('%s by %s.', action.capitalize(), self.env.user.name))
        return self.run_detail(run.id)

    @api.model
    def open_resource(self, workflow_id, key, record_id=None):
        w = self._workflow(workflow_id)
        if key in ('template', 'new_template'):
            self._template_editor()
            t = self._mail_template(record_id, w.source_model or 'pb.workflow.run') if key == 'template' else None
            return {'type': 'ir.actions.client', 'tag': 'pb_workflow_studio', 'name': _('Email template'),
                    'context': {'pb_workflow_id': w.id, 'pb_workflow_template_id': t.id if t else 'new'}}
        owner = next((r for r in self._ownership(w.source_model) if r['key'] == key), None)
        if not owner:
            raise UserError(_('This settings screen is not available.'))
        action = self.env.ref(owner['action']).read()[0]
        action['context'] = {'pb_lens': owner.get('lens', ''), 'pb_back': {
            'xmlid': 'pb_lifecycle.action_pb_workflow_studio', 'label': _('Workflow Studio'),
            'context': {'pb_workflow_id': w.id}}}
        return action

    @api.model
    def _cron_workflows(self):
        """One bounded worker; installation creates no active business flows."""
        for w in self.env['pb.workflow'].sudo().search([('enabled', '=', True)]):
            if w.published_id.definition['trigger']['kind'] != 'approval_applied':
                continue
            events = self.env['biz.approval.event'].sudo().search([
                ('id', '>', w.last_approval_event_id), ('kind', '=', 'applied'),
                ('company_id', '=', w.company_id.id),
                ('request_id.process_id', '=', w.published_id.process_id.id)], order='id', limit=100)
            for event in events:
                self._enqueue(w, event.res_id, event.request_id.submitter_uid.id,
                              'approval:%s:%s' % (w.id, event.id), request_id=event.request_id.id)
                internal(w).write({'last_approval_event_id': event.id})
        for event in self.env['pb.workflow.event'].sudo().search([('state', '=', 'pending')], order='id', limit=100):
            event._process()
        # A run marked "needs attention" may still have healthy steps waiting
        # on other paths (F4); those keep moving. The scan spans every company
        # on purpose: each run is then worked in its own company (`_service`).
        runs = self.env['pb.workflow.run'].sudo().search([
            '|', ('state', 'in', ['running', 'waiting']),
            '&', ('state', '=', 'failed'), ('step_ids.state', '=', 'waiting')], order='checked_at, id', limit=300)
        for run in runs:
            # A run already marked "needs attention" is scanned every pass
            # now; its history records a worker error once, not every minute.
            noted = run.state == 'failed'
            try:
                with self.env.cr.savepoint():
                    run._lock()
                    internal(run).write({'checked_at': fields.Datetime.now()})
                    for step in run.step_ids.filtered(lambda s: s.state == 'waiting'):
                        try:
                            with self.env.cr.savepoint():
                                self._check_waiting_step(run, step)
                        except (AccessError, UserError) as exc:
                            # One step's problem (record gone, moved company)
                            # stops that step, never its healthy siblings.
                            internal(step).write({'state': 'failed', 'error': str(exc)[:1000]})
                            run._log(_('Needs attention: %s', str(exc)[:400]), step)
                    run._advance()
            except Exception as exc:
                _logger.exception('Workflow run %s needs attention', run.id)
                internal(run).write({'state': 'failed'})
                if not noted:
                    run._log(str(exc)[:500])

    def _check_waiting_step(self, run, step):
        """The worker's look at one waiting step. Private: never callable by RPC."""
        if step.kind == 'wait':
            if step.config.get('wait_for'):
                if D.matches(step.config['wait_for'], run._condition_values(step.config)):
                    step._finish()
                elif step.wake_at <= fields.Datetime.now():
                    if step.config.get('on_timeout') == 'continue':
                        # WF2 P3b: "Carry on anyway" when time runs out.
                        step._finish()
                        note = _('Carried on after waiting %s.', self._wait_words(step.config))
                        internal(step).write({'error': note})
                        run._log(note, step)
                    else:
                        internal(step).write({'state': 'failed', 'error': _('The wait reached its deadline before the conditions matched. Check the record, then retry.')})
            elif step.wake_at <= fields.Datetime.now():
                step._finish()
        elif step.kind == 'stage_move':
            # Waiting for the record to reach the stage it follows.
            self._move_step(run, step, run._source() if run.source_model else None, step.config)
        elif step.kind == 'email':
            if not step.mail_id:
                internal(step).write({'state': 'failed', 'error': _('The queued message is missing. Check the mail service before retrying.')})
            elif step.mail_id.state == 'sent':
                step._finish()
            elif step.mail_id.state in ('exception', 'cancel'):
                internal(step).write({'state': 'failed', 'error': _('The mail service could not send this message. Fix delivery settings, then retry.')})
        elif step.kind == 'matrix' and not step.approval_id and step.config.get('mode') == 'follow':
            # "Follow" mode: wait until the record's own module sends it for
            # approval, then adopt that request. Never submits.
            step._follow(run._source())
        elif step.kind == 'matrix' and step.approval_id:
            req = step.approval_id
            if req.state == 'applied':
                step._finish()
            elif req.state in ('rejected', 'cancelled'):
                for s in run.step_ids:
                    s._cancel_activity()
                internal(run).write({'state': 'rejected' if req.state == 'rejected' else 'cancelled'})
                run._log(_('The approval request was %s.', req.state), step)
            elif req.state == 'returned':
                internal(step).write({'state': 'failed', 'error': _('Approval was returned. Correct the source record, then retry this step.'),
                                      'approval_id': False, 'approval_attempt': step.approval_attempt+1})
                internal(run).write({'state': 'failed'})
