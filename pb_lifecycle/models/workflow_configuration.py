"""Premium configuration over native Odoo records, never a second template store."""
import datetime
from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import html_sanitize
from . import workflow_definition as D


TEMPLATE_FIELDS = ('name', 'subject', 'body_html', 'email_from', 'email_to', 'email_cc', 'reply_to', 'lang')


class WorkflowConfiguration(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    def _validate(self, w, definition):
        errors = super()._validate(w, definition)
        if errors:
            return errors
        meta = {f['key']: f for f in self._source_fields(w.source_model)}
        meta.update({'person.user_id': {'type': 'many2one', 'relation': 'res.users'},
                     'person.group_ids': {'type': 'ids'}, 'workflow.stage': {'type': 'integer'},
                     'workflow.completed_stages': {'type': 'ids'}})
        for n in definition['nodes']:
            for f in n.get('form', {}).get('fields', []):
                meta['step.%s.%s' % (n['id'], f['id'])] = {**f, 'key': f['id']}
        checks = [('trigger', definition['scope']), ('trigger', definition['trigger'].get('before'))]
        for n in definition['nodes']:
            checks += [(n['id'], n.get('when')), (n['id'], n.get('wait_for'))]
            checks += [(n['id'], b.get('condition')) for b in n.get('branches', [])]
        for key, tree in checks:
            for rule in D.leaves(tree):
                f = meta.get(rule['field'], {})
                kind, op, value = f.get('type'), rule['op'], rule.get('value')
                choices = value if op in ('in', 'not_in') else [value]
                problem = False
                if op not in ('set', 'unset'):
                    if kind in ('integer', 'many2one', 'ids', 'lookup'):
                        problem = any(type(v) is not int for v in choices)
                    elif kind in ('float', 'monetary', 'number'):
                        problem = any(type(v) not in (int, float) for v in choices)
                    elif kind == 'boolean':
                        problem = any(type(v) is not bool for v in choices) or op not in ('eq', 'ne')
                    elif kind == 'selection':
                        problem = any(v not in {o[0] for o in f['options']} for v in choices)
                    elif kind == 'select':
                        problem = any(v not in f.get('options', []) for v in choices)
                    elif kind in ('text', 'char', 'textarea', 'email', 'date', 'datetime'):
                        problem = any(not isinstance(v, str) for v in choices)
                        if kind in ('date', 'datetime') and not problem:
                            try:
                                for v in choices:
                                    (datetime.date if kind == 'date' else datetime.datetime).fromisoformat(v)
                            except ValueError:
                                problem = True
                if op in ('contains', 'icontains', 'not_contains') and kind not in ('char', 'text', 'textarea', 'email', 'ids', 'multiselect'):
                    problem = True
                if op in ('set', 'unset') and kind == 'boolean':
                    problem = True
                if op in ('gt', 'gte', 'lt', 'lte') and kind not in ('integer', 'float', 'monetary', 'number', 'date', 'datetime'):
                    problem = True
                if rule['field'] in ('workflow.stage', 'workflow.completed_stages') and op not in ('set', 'unset'):
                    problem |= any(type(v) is not int or not 0 <= v < len(definition['stages']) for v in choices)
                if problem:
                    errors.append({'id': key, 'text': _('Choose a comparison and value that match the field type.'), 'severity': 'error'})
        return errors

    def _template_editor(self):
        self._design()
        if not (self.env.is_admin() or self.env.user.has_group('mail.group_mail_template_editor')):
            raise AccessError(_('You need email-template editing permission to change shared messages.'))

    @api.model
    def template_detail(self, workflow_id, template_id=None):
        w = self._workflow(workflow_id)
        self._template_editor()
        template = self._mail_template(template_id, w.source_model or 'pb.workflow.run') if template_id else self.env['mail.template']
        if template:
            template.check_access('write')
        else:
            template.check_access('create')
        return {'id': template.id or None, 'revision': str(template.write_date) if template else '',
                'values': {f: template[f] or '' for f in TEMPLATE_FIELDS} if template else
                          {f: '' for f in TEMPLATE_FIELDS},
                'model_label': self.env[w.source_model or 'pb.workflow.run']._description,
                'shared': bool(template),
                'fields': self._source_fields(w.source_model or 'pb.workflow.run')}

    def _template_values(self, payload):
        if not isinstance(payload, dict) or set(payload) - set(TEMPLATE_FIELDS):
            raise UserError(_('These template settings are not supported.'))
        if any(not isinstance(v, str) or len(v) > (200000 if k == 'body_html' else 2000) for k, v in payload.items()):
            raise UserError(_('Use a shorter message.'))
        if not payload.get('name', '').strip() or not payload.get('subject', '').strip():
            raise UserError(_('Give the message a name and a subject.'))
        result = dict(payload)
        # mail.template.body_html uses Odoo's email_outgoing sanitizer, which
        # preserves QWeb placeholders. Generic HTML sanitization removes them.
        # Preview output is sanitized after native rendering, never before it.
        return result

    @api.model
    def save_template(self, workflow_id, payload, template_id=None, revision=''):
        w = self._workflow(workflow_id)
        self._template_editor()
        vals = self._template_values(payload)
        if template_id:
            template = self._mail_template(template_id, w.source_model or 'pb.workflow.run')
            template.check_access('write')
            self.env.cr.execute('SELECT id FROM mail_template WHERE id=%s FOR UPDATE', [template.id])
            template.invalidate_recordset()
            if str(template.write_date) != revision:
                raise UserError(_('This shared template changed elsewhere. Reopen it before saving.'))
            template.write(vals)
        else:
            vals['model_id'] = self.env['ir.model']._get_id(w.source_model or 'pb.workflow.run')
            template = self.env['mail.template'].create(vals)
        return self.template_detail(w.id, template.id)

    @api.model
    def template_preview(self, workflow_id, payload, record_id):
        w = self._workflow(workflow_id)
        self._template_editor()
        vals = self._template_values(payload)
        source = self._source(w.source_model, record_id) if w.source_model else self._run(record_id)
        if not w.source_model and source.workflow_id.id != w.id:
            raise AccessError(_('Choose a run of this workflow.'))
        template = self.env['mail.template']
        result = {f: template._render_template(vals.get(f, ''), source._name, source.ids,
                    engine='qweb' if f == 'body_html' else 'inline_template')[source.id]
                  for f in ('subject', 'body_html', 'email_from', 'email_to', 'email_cc', 'reply_to')}
        result['body_html'] = html_sanitize(result['body_html'])
        return result

    @api.model
    def template_samples(self, workflow_id, term=''):
        w = self._workflow(workflow_id)
        if w.source_model:
            return self.search_records(w.id, term)
        return [{'id': r.id, 'name': r.name} for r in self.env['pb.workflow.run'].search([
            ('workflow_id', '=', w.id), ('company_id', '=', self.env.company.id),
            ('name', 'ilike', str(term)[:100])], limit=30) if self._readable_run(r)]

    @api.model
    def filter_choices(self, workflow_id, field, term='', selected=None):
        w = self._workflow(workflow_id)
        meta = next((f for f in self._source_fields(w.source_model) if f['key'] == field), {})
        if meta.get('type') != 'many2one':
            raise UserError(_('Choose a related-record field.'))
        model = self.env[meta['relation']]
        domain = [('display_name', 'ilike', str(term)[:100])]
        if 'company_id' in model._fields:
            domain += [('company_id', 'in', [False, self.env.company.id])]
        rows = model.search(domain, limit=60)
        if selected and type(selected) is int:
            extra = model.search([('id', '=', selected)] + (domain[1:]), limit=1)
            rows |= extra
        return [{'id': r.id, 'name': r.display_name} for r in rows]
