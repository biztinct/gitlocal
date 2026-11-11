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
import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from . import workflow_definition as D
from .workflow_models import internal
from .workflow_people import EMAIL, LINK_UNSUPPORTED

_logger = logging.getLogger(__name__)


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
            # WF2 P2b (D24, owner 11 Nov): the step waits and somebody is
            # asked to add the address (`_await_email`), instead of stopping.
            return {'mode': 'await_email', 'name': name, 'key': found['key'], 'label': found['label']}
        return {'mode': 'link', 'email': email, 'name': name, 'employee': self.env['hr.employee']}

    def _page_data(self, step, unsupported):
        """A participant's page shows the step and nothing of the record or
        the workflow around it (D18 privacy)."""
        data = super()._page_data(step, unsupported)
        if ((step.sudo().config or {}).get('owner') or {}).get('kind') == 'participant':
            data.update(workflow=data.get('company') or '', record='')
        return data

    # ================================================================ D24
    # "The candidate" has no email address: the step waits, and the person
    # the record names for it (Hiring's subject: the recruiter) gets a task
    # in the Approvals inbox — "Add an email for …", which opens the record.
    # Cover and teams apply as for any task. Nobody named → the workflow's
    # late-task role (D19) → whoever published it. Once the address is on the
    # record the worker sends the link once and the helper task closes.

    @staticmethod
    def _awaiting(step):
        return ((step.sudo().answers or {}).get('_await_email') or None) if step else None

    def _assign_person_step(self, run, step, node):
        owner = node.get('owner') or {}
        if owner.get('kind') == 'participant':
            who = self._resolve_people(run, owner)
            if who.get('mode') == 'await_email':
                return self._await_email(run, step, node, who)
        return super()._assign_person_step(run, step, node)

    def _email_keepers(self, run):
        """(person, team role) who is asked to add the address."""
        company = run.company_id
        source = run._source() if run.source_model else None
        if source is not None and hasattr(source, '_workflow_subject'):
            keeper = (self._subject(source).get('user') or self.env['res.users'])[:1]
            if keeper and keeper.active and not keeper.share and company in keeper.company_ids:
                return keeper, self.env['biz.approval.role']
        role = self._late_role(run.sudo().version_id.definition)
        if role and role.is_pool:
            if self._team_members(role, company, run):
                return self.env['res.users'], role
        elif role:
            holder = self._late_role_people(role, run)[:1]
            if holder:
                return holder, self.env['biz.approval.role']
        owner = self._workflow_owner(run)
        return (owner or self.env['res.users']), self.env['biz.approval.role']

    def _await_email(self, run, step, node, who):
        name = who['name']
        person, role = self._email_keepers(run)
        if not person and not role:
            raise UserError(_('%s has no email address on the record, and nobody could be found to add one.', name))
        try:
            deadline = self._task_deadline(run, node)
        except UserError:
            deadline = fields.Date.today() + timedelta(days=int(node.get('due', 2) or 2))
        answers = dict(step.sudo().answers or {})
        answers['_await_email'] = {'key': who['key'], 'name': name}
        vals = {'state': 'waiting', 'due_at': self._due_at(deadline), 'reminded_at': False,
                'passed_up_at': False, 'team_user_ids': [(5, 0, 0)], 'covered_user_id': False,
                'person_employee_id': False, 'answers': answers}
        step._cancel_activity()
        if role:
            members = self._team_members(role, run.company_id, run)
            vals.update(assignee_id=False, activity_id=False, team_user_ids=[(6, 0, members.ids)])
            internal(step).write(vals)
            run._log(_('%(who)s has no email address on the record. Waiting for someone on the team '
                       '%(team)s to add one.', who=name, team=role.name), step)
            stamp = fields.Datetime.to_string(step.started_at or fields.Datetime.now())
            for member in members:
                self.env['biz.approval.outbox'].sudo()._queue(
                    'task_reminder', member, payload=self._task_payload(run, step, 'new_team'),
                    dedupe='wf-team-new-%s-%s-%s' % (step.id, stamp, member.id))
            return True
        cover = self._covering(person, run.company_id)
        doer = cover or person
        activity = self._email_activity(run, step, doer, name, deadline)
        vals.update(assignee_id=doer.id, activity_id=activity.id if activity else False,
                    covered_user_id=person.id if cover else False)
        internal(step).write(vals)
        run._log(_('%(who)s has no email address on the record. Waiting for %(keeper)s to add one.',
                   who=name, keeper=doer.name), step)
        return True

    def _email_activity(self, run, step, doer, name, deadline):
        """The to-do sits on the record itself, so it opens the record."""
        source = run._source() if run.source_model else None
        model, res_id = (source._name, source.id) if source is not None else ('pb.workflow.run', run.id)
        return internal(self.env['mail.activity']).create({
            'res_model_id': self.env['ir.model']._get_id(model), 'res_id': res_id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'user_id': doer.id, 'summary': _('Add an email for %s', name),
            'note': _('A workflow needs to reach %s by email. Add their email address here; '
                      'the link then goes out by itself.', name),
            'date_deadline': deadline, 'workflow_step_id': step.id})

    def _check_waiting_step(self, run, step):
        waiting = self._awaiting(step)
        if not waiting:
            return super()._check_waiting_step(run, step)
        source = run._source() if run.source_model else None
        person = source.sudo()._workflow_participant(waiting.get('key')) or {} \
            if source is not None and hasattr(source, '_workflow_participant') else {}
        email = str(person.get('email') or '').strip()
        if not EMAIL.match(email):
            return False
        name = str(person.get('name') or '').strip() or waiting.get('name') or ''
        answers = dict(step.sudo().answers or {})
        answers.pop('_await_email', None)
        step._cancel_activity()
        internal(step).write({'answers': answers, 'assignee_id': False, 'activity_id': False,
                              'team_user_ids': [(5, 0, 0)], 'covered_user_id': False})
        run._log(_('An email address for %s was added.', name), step)
        self._send_link(run, step, email, name)
        return True

    def _recheck_awaiting_email(self, records):
        """WF2 P5a (P2b weak point): the moment an address is saved on a
        record that a workflow is waiting on, send the link at once instead
        of at the worker's next pass. Called by the area right after its own
        write (Hiring: the candidate's email). Each run is worked in its own
        company as the system (G1), in its own savepoint; nothing here may
        break the save that called it. The worker still checks every minute,
        so a failure here only costs that minute."""
        if not records:
            return 0
        done = 0
        try:
            steps = internal(self.env['pb.workflow.step']).search([
                ('state', '=', 'waiting'),
                ('run_id.source_model', '=', records._name),
                ('run_id.source_id', 'in', records.ids),
                ('run_id.state', 'in', ['running', 'waiting', 'failed'])])
        except Exception:   # noqa: BLE001
            _logger.exception('Workflow: could not look for steps waiting on an email')
            return 0
        for step in steps.filtered(self._awaiting):
            run = step.run_id
            try:
                with self.env.cr.savepoint():
                    service = run._service()
                    run = service.env['pb.workflow.run'].browse(run.id)
                    run._lock()
                    fresh = run.step_ids.filtered(lambda s: s.id == step.id)
                    if fresh.state == 'waiting' and service._check_waiting_step(run, fresh):
                        done += 1
                        run._advance()
            except Exception:   # noqa: BLE001
                _logger.exception('Workflow run %s: the instant email re-check failed; '
                                  'the worker will try again', run.id)
        return done

    def _task_card(self, step, mine=True):
        card = super()._task_card(step, mine)
        waiting = self._awaiting(step)
        if waiting:
            run = step.sudo().run_id
            card.update(title=_('Add an email for %s', waiting.get('name') or ''),
                        verb=_('Add an email'), task_kind='await_email')
            if mine and run.source_model:
                card['open'] = {'type': 'record', 'model': run.source_model, 'id': run.source_id}
        return card

    def _strip_row(self, run, viewer, full, home=False):
        """The record's strip says what is really waiting: an address, not
        the candidate's own step, and no "Do it now" into a page that would
        refuse it (the record itself is where the address goes)."""
        row = super()._strip_row(run, viewer, full, home)
        step = run.sudo().step_ids.filtered(lambda s: s.state == 'waiting' and self._awaiting(s))[:1]
        if not step:
            return row
        name = self._awaiting(step).get('name') or ''
        mine = step.assignee_id.id == viewer.id or (
            step.team_user_ids and not step.assignee_id and viewer in step.team_user_ids)
        row['task_id'] = None
        row.pop('task_name', None)
        if mine:
            row['own'] = True
        row['sentence'] = (_('Waiting for you: add an email for %s', name) if mine else
                           _('Waiting for %(who)s to add an email for %(name)s',
                             who=step.assignee_id.name or _('someone'), name=name))
        return row

    @api.model
    def answer(self, task_id, values=None, complete=True):
        step = self.env['pb.workflow.step'].sudo().browse(int(task_id or 0)).exists()
        waiting = self._awaiting(step)
        if waiting:
            raise UserError(_('This task is to add an email address for %s on the record. '
                              'The link then goes out by itself.', waiting.get('name') or _('them')))
        return super().answer(task_id, values, complete)

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
