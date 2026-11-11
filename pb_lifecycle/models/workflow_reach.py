"""WF2 P4b — "The candidate" (D18) and late with no manager (D19).

D18. An area may name people on its records who are not staff and never log
in, as "participants" in its contract (`participants: [{key, label,
audience}]`, and `_workflow_participant(key)` → {name, email}). Hiring names
"The candidate". Studio offers them in "Who does this?" and always reaches
them by the private email link (P4a). A link page cannot take a file or a
record choice, so a form with one is refused; a notice is read in the app, so
"Tell someone in the app" is refused; where the area already emails that
person at that stage, Review warns before a second email (R2e). The link page
for a participant shows only the step: no workflow name, no record name.

D19. "If a task is late and there is no manager, tell…" — a role from
Approvals › Who approves (one person, or a team), kept in the workflow's
definition so it is versioned with it. Pass-up order: line manager → that
role (resolved in the run's company) → the publisher.

No local is called `user` or `uid` in a method that calls `_()` (ledger G12).
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from . import workflow_definition as D
from .workflow_people import EMAIL, LINK_UNSUPPORTED


class WorkflowReach(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ================================================================ D18
    def _participants(self, model):
        if not model or model not in self.env:
            return []
        rows = self._declared(model).get('participants') or []
        return [{'key': str(p['key']), 'label': str(p.get('label') or p['key']),
                 'audience': str(p.get('audience') or 'other')}
                for p in rows if isinstance(p, dict) and p.get('key')]

    def _participant(self, model, key):
        return next((p for p in self._participants(model) if p['key'] == str(key or '')), None)

    @api.model
    def metadata(self, model='', workflow_id=None):
        result = super().metadata(model, workflow_id)
        result['participants'] = [{'key': p['key'], 'label': p['label']} for p in self._participants(model)]
        result['late_roles'] = [{'id': r.id, 'name': r.name, 'team': r.is_pool}
                                for r in self.env['biz.approval.role'].sudo().search([], order='name')]
        if isinstance(result.get('contract'), dict):
            result['contract']['participants'] = result['participants']
        return result

    def _owner_words(self, model, owner):
        owner = owner or {}
        if owner.get('kind') == 'participant':
            found = self._participant(model, owner.get('key'))
            return found['label'] if found else _('Someone this record names')
        return super()._owner_words(model, owner)

    def _owner_audience(self, owner):
        owner = owner or {}
        if owner.get('kind') == 'participant':
            return str(owner.get('audience') or 'candidate')
        return super()._owner_audience(owner)

    def _check_owner(self, model, company, owner):
        if isinstance(owner, dict) and owner.get('kind') == 'participant':
            raise UserError(_('Choose a staff person to move records into this stage.'))
        return super()._check_owner(model, company, owner)

    def _new_step_issues(self, w, d, n):
        out = list(super()._new_step_issues(w, d, n))
        owner = n.get('owner') or {}
        if owner.get('kind') != 'participant' or n['type'] not in D.PEOPLE + ('notify',):
            return out
        found = self._participant(w.source_model or '', owner.get('key'))
        if not found:
            return out + [('bad_participant', _('Choose someone this kind of record names.'))]
        if n['type'] == 'notify':
            return out + [('participant_notice', _('A notice is read inside the app, and %s has no login. '
                                                   'Use “Ask someone to confirm” or a form instead.',
                                                   self._lower(found['label'])))]
        bad = [f.get('label', '') for f in (n.get('form') or {}).get('fields', [])
               if f.get('type') in LINK_UNSUPPORTED]
        if bad:
            out.append(('participant_cannot', _('%(who)s answers by email link, and a link page cannot take %(fields)s. '
                                                'Remove them, or choose someone else.',
                                                who=found['label'],
                                                fields=', '.join('“%s”' % b for b in bad))))
        return out

    @staticmethod
    def _lower(text):
        text = str(text or '')
        return text[:1].lower() + text[1:] if text.startswith(('The ', 'Their ')) else text

    def _people_notes(self, w, d):
        notes = list(super()._people_notes(w, d))
        people = [n for n in d.get('nodes', []) if n.get('type') in D.PEOPLE]
        for n in people:
            owner = n.get('owner') or {}
            if owner.get('kind') != 'participant':
                continue
            found = self._participant(w.source_model or '', owner.get('key'))
            if found:
                notes.append({'id': n['id'], 'tone': 'info', 'code': 'participant_link',
                              'text': _('“%(step)s” goes to %(who)s by email link. If there is no email address '
                                        'on the record, the step stops and needs a look.',
                                        step=n.get('title', ''), who=self._lower(found['label']))})
        if people and not self._late_role(d):
            notes.append({'id': 'trigger', 'tone': 'info', 'code': 'late_fallback',
                          'text': _('If a task is late and the person has no manager, the person who published '
                                    'this workflow is told. You can name someone else in Settings.')})
        return notes

    def _repeat_warnings(self, w, d):
        out = list(super()._repeat_warnings(w, d))
        model = w.source_model
        if not model:
            return out
        warned = {i['id'] for i in out}
        effects = None
        binds = {i: self._bind_key(s) for i, s in enumerate(d['stages'])}
        for n in d['nodes']:
            owner = n.get('owner') or {}
            if n['type'] not in D.PEOPLE or owner.get('kind') != 'participant' or n['id'] in warned:
                continue
            at = binds.get(n.get('stage'))
            found = self._participant(model, owner.get('key'))
            if at is None or not found:
                continue
            if effects is None:
                effects = self._existing(model, w.company_id, exclude=w if w.id else None)
            hit = next((e for e in effects if e['kind'] == 'message' and str(e['stage']) == str(at)
                        and e['audience'] == found['audience']), None)
            if hit:
                out.append({'id': n['id'], 'code': 'repeats_existing', 'severity': 'warning',
                            'acknowledged': bool(n.get('ack_repeat')), 'existing': hit.get('text', ''),
                            'existing_source': hit.get('source', ''),
                            'text': _('%(owner)s already emails %(who)s here: %(text)s This step would send a second email.',
                                      owner=hit['owner'], who=self._lower(found['label']),
                                      text=hit['text'][:1].lower() + hit['text'][1:])})
        return out

    def _validate(self, w, definition):
        issues = super()._validate(w, definition)
        if any(i.get('code') in D.STRUCTURAL for i in issues) or not isinstance(definition, dict):
            return issues
        late = definition.get('late_tell')
        if late not in (None, {}, False):
            role = self.env['biz.approval.role'].sudo().browse(
                late.get('id') if isinstance(late, dict) and type(late.get('id')) is int else 0).exists()
            if not role:
                issues.append({'id': 'trigger', 'code': 'late_tell', 'severity': 'error',
                               'text': _('Choose who is told about late tasks from Approvals › Who approves.')})
        return issues

    def _resolve_people(self, run, owner):
        owner = owner or {}
        if owner.get('kind') != 'participant':
            return super()._resolve_people(run, owner)
        found = self._participant(run.source_model or '', owner.get('key'))
        source = run._source() if run.source_model else None
        if not found or source is None or not hasattr(source, '_workflow_participant'):
            raise UserError(_('This kind of record does not name that person any more. Edit the step.'))
        person = source.sudo()._workflow_participant(found['key']) or {}
        name = str(person.get('name') or '').strip() or found['label']
        email = str(person.get('email') or '').strip()
        if not EMAIL.match(email):
            raise UserError(_('%s has no email address on the record, so this cannot reach them.', name))
        return {'mode': 'link', 'email': email, 'name': name, 'employee': self.env['hr.employee']}

    def _page_data(self, step, unsupported):
        """A participant's page shows the step and nothing of the record or
        the workflow around it (D18 privacy)."""
        data = super()._page_data(step, unsupported)
        if ((step.sudo().config or {}).get('owner') or {}).get('kind') == 'participant':
            data.update(workflow=data.get('company') or '', record='')
        return data

    # ================================================================ D19
    def _late_role(self, definition):
        late = (definition or {}).get('late_tell')
        if not isinstance(late, dict) or type(late.get('id')) is not int:
            return self.env['biz.approval.role']
        return self.env['biz.approval.role'].sudo().browse(late['id']).exists()

    def _late_role_people(self, role, run):
        """The named role's people in the run's company (a team: everyone
        on it). Staff logins of that company only."""
        company = run.company_id
        if role.is_pool:
            return self._team_members(role, company, run)
        source = run._source() if run.source_model else None
        scopes = source._approval_context().get('scope_keys', ['']) \
            if source is not None and hasattr(source, '_approval_context') else ['']
        row, _via = self.env['biz.approval.responsibility'].sudo().resolve(company, role, scopes)
        holder = row.user_id if row else self.env['res.users']
        return holder.filtered(lambda h: h.active and not h.share and company in h.company_ids)

    def _pass_up_people(self, step, run):
        people, told = super()._pass_up_people(step, run)
        if told == 'manager':
            return people, told
        role = self._late_role(run.sudo().version_id.definition)
        if role:
            holders = self._late_role_people(role, run) - step.assignee_id
            if holders:
                return holders, role.name
        return people, told

    def _passed_up_words(self, step):
        if not step.passed_up_at or not step.passed_up_to:
            return ''
        day = format_date(self.env, fields.Datetime.context_timestamp(self, step.passed_up_at).date(), date_format='d MMM')
        if step.passed_up_to == 'manager':
            return _('Their manager was told on %s', day)
        if step.passed_up_to == 'publisher':
            return _('The person who published this workflow was told on %s', day)
        return _('%(role)s was told on %(day)s', role=step.passed_up_to, day=day)

    @api.model
    def progress(self, run_id):
        result = super().progress(run_id)
        steps = {s.id: s for s in self.env['pb.workflow.step'].sudo().browse([r['id'] for r in result['steps']])}
        for row in result['steps']:
            s = steps.get(row['id'])
            words = self._passed_up_words(s) if s else ''
            if words:
                row['passed_up'] = words
        return result
