"""The eight step types WF2 P3b adds, run by the system (R3, ledger G1).

Every effect here is a registered, guarded operation that REUSES what already
exists (owner rulings R2/R2a, D8):

  * Move to a stage   → the user-made stage layer (`_set_position`), never the
                        record's own status;
  * Send back         → resets steps of this run only (no effect outside it);
  * Update the record → the area's own `_workflow_update` door, for a value
                        the area declared safe (`safe_fields`);
  * Create something  → a DRAFT in the letters library or in announcements;
                        sending keeps its own approval, Studio never sends;
  * Tell someone      → an in-app inbox notification, the approval outbox's
                        way, but never an email and never a to-do;
  * Ask to confirm    → a person step (see `workflow_models._execute`);
  * Start another     → the normal start queue (`_enqueue`), one active run
                        per workflow and record, at most three hand-overs;
  * Stop here         → closes this run only.

No local is called `user` or `uid` in a method that calls `_()` (ledger G12).
"""
import math
import re
from datetime import timedelta

import pytz
from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from . import workflow_definition as D
from .workflow_models import internal

TOKEN = re.compile(r'\{\{\s*([a-zA-Z0-9_.-]{1,120})\s*\}\}')
FEEDS, TYPE_WORDS = D.FEEDS, D.TYPE_WORDS


class WorkflowSteps(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ------------------------------------------------------------ creators
    def _creators(self):
        """What "Create something" can make, each reusing its own feature.
        A creator is offered only when its module is installed."""
        return [
            {'key': 'letter', 'label': _('A letter'), 'model': 'pb.hr.letter',
             'template_model': 'pb.letter.template', 'needs_subject': True,
             'available': 'pb.letter.template' in self.env and 'pb.hr.letter' in self.env,
             'hint': _('A draft letter for the person this is about, from your letters library. '
                       'Sending it still needs its own approval.'),
             'made': _('Draft letter')},
            {'key': 'announcement', 'label': _('An announcement'), 'model': 'pb.hr.comm.post',
             'template_model': 'pb.hr.comm.template', 'needs_subject': False,
             'available': 'pb.hr.comm.post' in self.env and 'pb.hr.comm.template' in self.env,
             'hint': _('A draft announcement from one of your templates. It then follows its own sign-off '
                       'before it goes out.'),
             'made': _('Draft announcement')},
        ]

    def _creator(self, key):
        return next((c for c in self._creators() if c['key'] == key), None)

    def _creator_templates(self, creator, company, readable=True):
        """Templates a designer can pick (read as them when `readable`)."""
        if not creator or not creator['available']:
            return self.env['res.partner'].browse()
        Template = self.env[creator['template_model']]
        if readable and not Template.has_access('read'):
            return Template.browse()
        Template = Template if readable else Template.sudo()
        if creator['key'] == 'announcement':
            return Template.usable_for(company.id)
        return Template.search(['|', ('company_id', '=', False), ('company_id', '=', company.id)], limit=200)

    def _creator_metadata(self, model, company):
        rows = []
        has_subject = bool(model) and hasattr(self.env[model], '_workflow_subject')
        for c in self._creators():
            reason = ''
            if not c['available']:
                reason = _('This app is not switched on here.')
            elif c['needs_subject'] and not has_subject:
                reason = _('Letters are written for the person a record is about, and this kind of record does not say who that is.')
            templates = self._creator_templates(c, company) if c['available'] else []
            rows.append({'key': c['key'], 'label': c['label'], 'hint': c['hint'], 'reason': reason,
                         'templates': [{'id': t.id, 'name': t.display_name} for t in templates]})
        return rows

    # ----------------------------------------------------------- safe values
    def _safe_spec(self, model, key):
        return next((f for f in self._contract(model).get('safe_fields', []) if f.get('key') == key), None)

    def _safe_value(self, spec, value, company):
        """A value checked against the kind the area declared, or a refusal."""
        kind = spec.get('type')
        label = spec.get('label') or spec.get('key')
        bad = UserError(_('“%(label)s” needs %(kind)s.', label=label, kind=_(TYPE_WORDS.get(kind, 'a value'))))
        if kind == 'text':
            if value is None:
                return ''
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                value = str(value)
            if not isinstance(value, str) or len(value) > 2000:
                raise bad
            return value
        if kind == 'number':
            if type(value) not in (int, float) or not math.isfinite(value):
                raise bad
            return value
        if kind == 'date':
            if not isinstance(value, str):
                raise bad
            try:
                return fields.Date.to_string(fields.Date.from_string(value))
            except (ValueError, TypeError):
                raise bad
        if kind == 'yesno':
            if type(value) is not bool:
                raise bad
            return value
        if kind == 'choice':
            keys = {str(o['key']) if isinstance(o, dict) else str(o) for o in spec.get('options') or []}
            if str(value) not in keys:
                raise bad
            return str(value)
        if kind == 'person':
            person = self.env['res.users'].sudo().browse(value if type(value) is int else 0).exists()
            if not person or not person.active or person.share or company not in person.company_ids:
                raise bad
            return person.id
        raise UserError(_('This value cannot be set by a workflow.'))

    def _value_words(self, spec, value):
        if spec.get('type') == 'choice':
            return next((o.get('label') for o in spec.get('options') or [] if isinstance(o, dict)
                         and str(o.get('key')) == str(value)), str(value))
        if spec.get('type') == 'yesno':
            return _('Yes') if value else _('No')
        if spec.get('type') == 'person':
            return self.env['res.users'].sudo().browse(value).name or ''
        text = str(value if value is not None else '')
        return text if len(text) <= 80 else text[:77] + '…'

    # --------------------------------------------------------------- texts
    def _fill(self, text, run, source):
        """A notice's words with {{detail}} holes filled by substitution,
        never by evaluation; an unknown hole stays as typed (as letters do)."""
        values = run._values()
        def one(match):
            key = match.group(1)
            # WF2 P5c: a line's own details ({{line.amount}}) fill the same way.
            if key.startswith(('step.', 'line.')):
                value = values.get(key)
                if value is None:
                    return match.group(0)
                if isinstance(value, bool):
                    return _('Yes') if value else _('No')
                if isinstance(value, list):
                    return ', '.join(str(v) for v in value)
                return str(value)
            if source is None or key not in source._fields or key not in {f['key'] for f in self._source_fields(source._name)}:
                return match.group(0)
            field, value = source._fields[key], source.sudo()[key]
            if field.type == 'many2one':
                return value.display_name or ''
            if field.type == 'selection':
                return dict(field._description_selection(self.env)).get(value, value or '')
            if field.type == 'boolean':
                return _('Yes') if value else _('No')
            return '' if value is False or value is None else str(value)
        return TOKEN.sub(one, text or '')

    # --------------------------------------------------------- the step kinds
    def _wake_at(self, run, node):
        """When a wait ends: hours, days, or working days on the company's
        calendar (the one task deadlines already use)."""
        if node.get('unit') == 'working':
            days = int(node.get('amount') or max(1, round(node['hours'] / 24)))
            calendar = run.company_id.resource_calendar_id
            if not calendar:
                raise UserError(_('Set the company working calendar before waiting in working days.'))
            planned = calendar.plan_days(days + 1, pytz.utc.localize(fields.Datetime.now()), compute_leaves=True)
            if not planned:
                raise UserError(_('The company calendar has no available working days.'))
            return planned.astimezone(pytz.utc).replace(tzinfo=None)
        return fields.Datetime.now() + timedelta(hours=node['hours'])

    def _skip_step(self, run, step, reason):
        step._cancel_activity()
        internal(step).write({'state': 'skipped', 'error': reason, 'done_at': fields.Datetime.now()})
        run._log(_('Skipped %(step)s: %(why)s', step=step.name, why=reason), step)

    def _move_step(self, run, step, source, node):
        """Move to a stage: one of YOUR stages, never the area's status."""
        target = node.get('target') or {}
        stage = self.env['pb.workflow.stage'].sudo().browse(int(target.get('id') or 0)).exists()
        if not stage or not stage.active or stage.company_id != run.company_id:
            raise UserError(_('The stage this step moves to no longer exists. Edit the step.'))
        if run.source_model:
            if stage.source_model != run.source_model or stage.workflow_id:
                raise UserError(_('“%s” belongs to another kind of record. Edit the step.', stage.name))
            contract = self._contract(run.source_model, source)
            status = self._status_value(contract, source)
            order = [s for s in contract['stages'] if not s.get('exit')]
            keys = [str(s['key']) for s in order]
            exit_ = next((s for s in contract['stages'] if s.get('exit') and str(s['key']) == str(status)), None)
            anchor = next((s for s in order if str(s['key']) == str(stage.anchor_value)), None)
            if exit_:
                return self._skip_step(run, step, _('This is now %(exit)s, so it was not moved to %(stage)s.',
                                                    exit=exit_['name'], stage=stage.name))
            if not anchor:
                raise UserError(_('“%s” follows a stage that no longer exists.', stage.name))
            if str(status) != str(stage.anchor_value):
                if str(status) in keys and keys.index(str(status)) < keys.index(str(anchor['key'])):
                    reason = _('Waiting for this to reach %s.', anchor['name'])
                    if step.state != 'waiting' or step.error != reason:
                        internal(step).write({'state': 'waiting', 'error': reason})
                        run._log(reason, step)
                    return
                return self._skip_step(run, step, _('This is already past %(anchor)s, so it was not moved to %(stage)s.',
                                                    anchor=anchor['name'], stage=stage.name))
            self._set_position(run.source_model, run.source_id, stage, run.company_id, run=run, by_workflow=True)
        else:
            if stage.workflow_id != run.workflow_id:
                raise UserError(_('“%s” belongs to another process. Edit the step.', stage.name))
            self._set_position('pb.workflow.run', run.id, stage, run.company_id, run=run, by_workflow=True)
        internal(step).write({'error': False})
        step._finish()

    def _send_back(self, run, step, node):
        """Send back for changes: the target and the steps after it, up to
        this one, start again; the target's person sees the latest note."""
        # WF2 P5c: on one line of a repeat, the repeat's steps are the path.
        d = run._definition()
        count = int(step.choice or 0) if str(step.choice or '').isdigit() else 0
        if count >= D.SEND_BACK_LIMIT:
            raise UserError(_('This has gone back three times. Someone should look at it.'))
        target = node.get('target')
        parent_map = D.parents(d)
        if target not in d['order']:
            raise UserError(_('The step this sends back to is not on the main path any more. Edit the step.'))
        steps = {s.key: s for s in run.step_ids}
        twice = [steps[k].name for k in D.between(d, target, step.key, parent_map)
                 if k in steps and steps[k].kind in D.ONCE_ONLY and steps[k].state == 'done']
        if twice:
            raise UserError(_('Steps in between would run twice: %s.', ', '.join(twice)))
        people = run.step_ids.filtered(lambda s: s.kind in D.PEOPLE and s.state == 'done' and s.done_at)
        latest = people.sorted(lambda s: (s.done_at, s.id), reverse=True)[:1]
        note = (latest.answers or {}).get('comment') if latest else ''
        sender = latest.assignee_id.name if latest else ''
        for key in D.reset_range(d, target, step.key, parent_map):
            s = steps.get(key)
            if not s:
                continue
            s._cancel_activity()
            answers = dict(s.answers or {})
            if s.kind in ('task', 'confirm'):
                for k in ('outcome', 'outcome_label', 'comment'):
                    answers.pop(k, None)
            answers.pop('_sent_back', None)
            if key == target:
                answers['_sent_back'] = {'by': sender or '', 'note': note or '', 'from': step.name}
            internal(s).write({'state': 'pending', 'error': False, 'done_at': False, 'started_at': False,
                               'wake_at': False, 'mail_id': False, 'assignee_id': False, 'answers': answers,
                               'choice': str(count + 1) if s.id == step.id else False})
        run._log(_('Sent back to %(target)s (%(n)s of %(limit)s).', target=steps[target].name,
                   n=count + 1, limit=D.SEND_BACK_LIMIT), step)

    def _update_step(self, run, step, source, node):
        """Update the record: one value the area opened, through its door."""
        if not run.source_model:
            raise UserError(_('A new process has no record to update.'))
        key = node.get('field')
        contract = self._contract(run.source_model, source)
        spec = self._safe_spec(run.source_model, key)
        if not spec or key == contract.get('stage_field') or not hasattr(source, '_workflow_update'):
            raise UserError(_('%(area)s has not opened this value to workflows.', area=contract['area']))
        value = run._values().get(node['value_from']) if node.get('value_from') else node.get('value')
        value = self._safe_value(spec, value, run.company_id)
        source._workflow_update(key, value)
        # WF2 P4a: an area may give its own words ("Added the tag “%s”.").
        run._log(spec['done_words'] % self._value_words(spec, value) if spec.get('done_words') else
                 _('Set %(label)s to %(value)s.', label=spec.get('label') or key,
                   value=self._value_words(spec, value)), step)
        step._finish()

    def _create_step(self, run, step, source, node):
        """Create something: a draft through the existing feature, once."""
        made = self._made(step)
        if made:
            # Retried after a later problem: never create twice.
            step._finish()
            return made
        creator = self._creator(node.get('creator'))
        if not creator or not creator['available']:
            raise UserError(_('This app is not switched on here any more, so nothing was created.'))
        Template = self.env[creator['template_model']].sudo()
        template = Template.browse(int(node.get('template_id') or 0)).exists()
        usable = self._creator_templates(creator, run.company_id, readable=False)
        if not template or template not in usable:
            raise UserError(_('The template this step starts from is not available any more. Edit the step.'))
        if creator['key'] == 'letter':
            subject = self._subject(source) if source is not None and source._name != 'pb.workflow.run' else {}
            employee = subject.get('employee')
            if not employee:
                raise UserError(_('This is not about an employee, so there is nobody to write a letter for.'))
            employee = employee[:1]
            if employee.company_id and employee.company_id != run.company_id:
                raise UserError(_('%s works for another company.', employee.name))
            record = self.env['pb.hr.letter'].sudo().create({
                'employee_id': employee.id, 'template_id': template.id, 'company_id': run.company_id.id,
                'subject': template.subject or template.name})
            words = _('Draft letter created for %(who)s: %(what)s.', who=employee.name, what=template.name)
        else:
            vals = {'template_id': template.id, 'subject': template.subject or template.name,
                    'body_html': template.body_html, 'company_id': run.company_id.id}
            if template.poster_ids:
                vals['poster_ids'] = [(6, 0, template.poster_ids.ids)]
            starter = run.initiator_id
            if starter and starter.active and not starter.share and run.company_id in starter.company_ids \
                    and starter.id != self.env.ref('base.user_root').id:
                vals['responsible_user_id'] = starter.id
            record = self.env['pb.hr.comm.post'].sudo().create(vals)
            words = _('Draft announcement created: %s.', record.subject)
        internal(step).write({'choice': '%s,%s' % (record._name, record.id)})
        run._log(words, step)
        step._finish()
        return record

    def _made(self, step):
        """What a "Create something" step made, if it still exists."""
        ref = str(step.choice or '')
        if ',' not in ref:
            return None
        model, ident = ref.rsplit(',', 1)
        if model not in self.env or not ident.isdigit():
            return None
        return self.env[model].sudo().browse(int(ident)).exists() or None

    def _notify_step(self, run, step, source, node):
        """Tell someone in the app: an inbox notice, no email, no to-do."""
        owner = node.get('owner') or {}
        if owner.get('kind') == 'subject':
            subject = self._subject(source) if source is not None else {}
            login = subject.get('user') or self.env['res.users']
            if not login or not login[:1].active or login[:1].share:
                name = (subject.get('employee') or self.env['hr.employee'])[:1].name or login[:1].name \
                    or _('The person this is about')
                return self._skip_step(run, step, _('%s has no login to show this to.', name))
            person = login[:1]
        else:
            person = self.env['res.users'].sudo().browse(self._resolve_owner(run, owner)).exists()
        if not person or not person.active or person.share:
            return self._skip_step(run, step, _('%s has no login to show this to.', person.name or _('That person')))
        target = source if source is not None and hasattr(source, '_notify_thread_by_inbox') else run
        try:
            if target is not run and not target.with_user(person).has_access('read'):
                target = run
        except (AccessError, UserError):
            target = run
        body = Markup('<p>%s</p>') % escape(self._fill(node.get('text'), run, source)).replace('\n', Markup('<br/>'))
        message = self.env['mail.message'].sudo().create({
            'model': target._name, 'res_id': target.id, 'body': body,
            'subject': run.name, 'message_type': 'notification',
            'subtype_id': self.env.ref('mail.mt_note').id,
            'author_id': run.company_id.partner_id.id})
        # Named on the step first (WF2 P5c): the inbox reads the run as the
        # person told, and a run lets the people on its steps read it — a
        # notice from one line of a repeat (or a new process the person did
        # not start) otherwise failed with the framework's refusal (G72).
        internal(step).write({'assignee_id': person.id})
        # The approval outbox's way of telling someone in the app, without
        # the email a person set to "by email" would otherwise get.
        target.sudo()._notify_thread_by_inbox(message, [{'id': person.partner_id.id, 'uid': person.id, 'notif': 'inbox'}])
        run._log(_('Told %s in the app.', person.name), step)
        step._finish()

    def _chain_depth(self, run):
        """How many hand-overs led to this run (each started by "Start another
        workflow", recorded in its start key)."""
        depth, guard = 0, 0
        Event = self.env['pb.workflow.event'].sudo()
        while run and guard < 10:
            event = Event.search([('run_id', '=', run.id)], limit=1)
            parts = (event.key or '').split(':')
            if not event or parts[0] != 'chain' or len(parts) < 2 or not parts[1].isdigit():
                break
            depth, guard = depth + 1, guard + 1
            run = self.env['pb.workflow.run'].sudo().browse(int(parts[1])).exists()
        return depth

    def _start_step(self, run, step, node):
        """Start another workflow for the same record; does not wait for it."""
        target = self.env['pb.workflow'].sudo().browse(int(node.get('workflow_id') or 0)).exists()
        if not target or target.company_id != run.company_id:
            raise UserError(_('The workflow this hands over to no longer exists. Edit the step.'))
        if target == run.workflow_id:
            raise UserError(_('A workflow cannot start itself.'))
        if not target.enabled or not target.published_id or target.component:
            raise UserError(_('“%s” is not switched on, so it could not start. Switch it on, then retry.', target.name))
        if (target.source_model or '') != (run.source_model or '') or \
                target.published_id.definition['trigger']['kind'] != 'manual':
            raise UserError(_('“%s” no longer starts this way for these records. Edit the step.', target.name))
        if self._chain_depth(run) >= D.CHAIN_LIMIT:
            raise UserError(_('This would be the fourth workflow handed over in a row. Workflows can hand over three times at most.'))
        key = 'chain:%s:%s' % (run.id, step.key)
        event = self._enqueue(target, run.source_id if run.source_model else None, run.initiator_id.id, key)
        if event.key != key:
            note = _('%s is already running for this record.', target.name)
            step._finish()
            internal(step).write({'error': note})
            run._log(note, step)
            return
        event._process()
        step._finish()
        if event.run_id:
            internal(step).write({'choice': 'pb.workflow.run,%s' % event.run_id.id})
            run._log(_('Started %s.', target.name), step)
        else:
            note = _('%s did not start: its filters do not match this record.', target.name) \
                if event.state == 'excluded' else (event.error or _('%s did not start.', target.name))
            internal(step).write({'error': note[:1000]})
            run._log(note[:400], step)

    # --------------------------------------------------- words for screens
    def _wait_words(self, node):
        amount = node.get('amount')
        unit = node.get('unit', 'hours')
        if unit == 'working':
            n = int(amount or max(1, round(node.get('hours', 24) / 24)))
            return _('%s working day', n) if n == 1 else _('%s working days', n)
        if unit == 'days':
            n = int(amount or max(1, round(node.get('hours', 24) / 24)))
            return _('%s day', n) if n == 1 else _('%s days', n)
        hours = node.get('hours', 1)
        hours = int(hours) if float(hours).is_integer() else hours
        return _('%s hour', hours) if hours == 1 else _('%s hours', hours)

    def _would(self, w):
        """The Try it out line of each new step: what it would do, in words.
        Nothing is executed or created."""
        model = w.source_model or ''
        nodes = {n['id']: n for n in (w.draft or {}).get('nodes', [])}
        def who(owner):
            return self._owner_words(model, owner or {})
        def describe(n):
            kind = n.get('type')
            if kind == 'stage_move':
                stage = self.env['pb.workflow.stage'].sudo().browse(int((n.get('target') or {}).get('id') or 0)).exists()
                return _('Would move this to %s', stage.name) if stage else None
            if kind == 'send_back':
                target = nodes.get(n.get('target'))
                return _('Would send it back to %s. The steps from there run again.', target['title']) if target else None
            if kind == 'end':
                reason = str(n.get('reason') or '').strip()
                return _('Would stop here: %s', reason) if reason else _('Would stop here')
            if kind == 'update':
                spec = self._safe_spec(model, n.get('field')) if model else None
                if not spec:
                    return None
                if n.get('value_from'):
                    source = nodes.get(str(n['value_from']).split('.')[1]) if str(n['value_from']).count('.') == 2 else None
                    return _('Would set %(label)s from the answer to %(step)s', label=spec.get('label'),
                             step=source['title'] if source else _('an earlier step'))
                if spec.get('would_words'):
                    return spec['would_words'] % self._value_words(spec, n.get('value'))
                return _('Would set %(label)s to %(value)s', label=spec.get('label'), value=self._value_words(spec, n.get('value')))
            if kind == 'create':
                creator = self._creator(n.get('creator'))
                template = self.env[creator['template_model']].sudo().browse(int(n.get('template_id') or 0)).exists() \
                    if creator and creator['available'] else None
                if not template:
                    return None
                return (_('Would make a draft letter from %s', template.display_name) if creator['key'] == 'letter'
                        else _('Would make a draft announcement from %s', template.display_name))
            if kind == 'notify':
                return _('Would tell %s in the app', _lower(who(n.get('owner'))))
            if kind == 'confirm':
                return _('Would ask %s to confirm', _lower(who(n.get('owner'))))
            if kind == 'start':
                target = self.env['pb.workflow'].sudo().browse(int(n.get('workflow_id') or 0)).exists()
                return _('Would start %s', target.name) if target else None
            if kind == 'task' and len(D.buttons(n)) > 1:
                return _('Asks %(who)s: %(choices)s', who=_lower(who(n.get('owner'))),
                         choices=' / '.join(b['label'] for b in D.buttons(n)))
            return None
        return describe

    # ------------------------------------------------------- metadata, doors
    @api.model
    def metadata(self, model='', workflow_id=None):
        result = super().metadata(model, workflow_id)
        company = self._company()
        result['creators'] = self._creator_metadata(model, company)
        result['safe_fields'] = list(self._contract(model).get('safe_fields') or []) if model else []
        others = self.env['pb.workflow'].sudo().search([
            ('company_id', '=', company.id), ('source_model', '=', model or False), ('component', '=', False)]
            + ([('id', '!=', int(workflow_id))] if workflow_id else []), limit=200)
        result['start_targets'] = [{
            'id': o.id, 'name': o.name, 'enabled': o.enabled, 'published': bool(o.published_id),
            'manual': ((o.published_id.definition if o.published_id else o.draft) or {}).get('trigger', {}).get('kind', 'manual') == 'manual',
        } for o in others]
        return result

    @api.model
    def stage_add_area(self, model, name, after_key):
        """A new stage that belongs to the area (D10, Hiring): made by the
        area's own door, with the area's own permission check. Studio keeps
        no stage of its own for such records."""
        self._design()
        if model not in {r['key'] for r in self._models()}:
            raise AccessError(_('This record type is not available.'))
        contract = self._contract(model)
        obj = self.env[model]
        if not contract.get('adds_stages') or not hasattr(obj, '_workflow_add_stage'):
            raise UserError(_('%s stages are added in its own set-up.', contract['area'] or contract['label']))
        after = next((s for s in contract['stages'] if str(s['key']) == str(after_key)), None)
        if not after or not after.get('id'):
            raise UserError(_('Choose the stage the new one comes after.'))
        made = obj._workflow_add_stage(name, after['id'])
        catalogue = self.stage_catalogue(model)
        catalogue['added'] = {'key': made.get('key'), 'note': made.get('note', '')}
        return catalogue


def _lower(text):
    """Lower-case an ordinary first word only; a person's name keeps its
    capital (ledger G25)."""
    text = str(text or '')
    first = text.split(' ', 1)[0]
    return first.lower() + text[len(first):] if first in ('The', 'Their', 'A', 'An', 'Person') else text
