"""The module contract: what a business area says about its own records.

Each area may declare (duck-typed, no dependency on this module):

  * `_workflow_capabilities()` — label, area, stage field, stages in order
    (with what moves a record into each, exits last), what the area itself
    already does (`effects`), the operations Studio may call (`actions`),
    its settings screens (`owners`) and switches such as `submits_itself`;
  * `_workflow_subject()` — who the record is about, and their manager by
    the area's own rule;
  * `_workflow_stage_options(record)` — stages that are rows (Hiring);
  * `_workflow_effects(company)` — effects that depend on configuration;
  * `_workflow_execute(key, params)` / `_workflow_rename_stage(...)`.

Studio reads the contract and never re-implements it. A record type without
one still works: its stages are discovered from its form (`source:
'discovered'`). "Already happens" (`existing_behaviour`) is the one place a
designer sees what the area, the approval engine, existing rules and other
workflows already do, and `_validate` warns before a step repeats one (R2).
"""
from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from odoo.addons.biz_approval_workflow.models import definition as AD

from . import workflow_definition as D

MATRIX_ACTION = 'pb_approval_config.action_pb_approval_matrix'
TRIGGER_WORDS = {
    'on_create': 'when a record is created', 'on_write': 'when a record is changed',
    'on_create_or_write': 'when a record is created or changed', 'on_unlink': 'when a record is deleted',
    'on_change': 'while a form is being filled in', 'on_time': 'at a set time',
    'on_time_created': 'some time after a record is created', 'on_time_updated': 'some time after a record changes',
    'on_stage_set': 'when the stage changes', 'on_state_set': 'when the status changes',
    'on_priority_set': 'when the priority changes', 'on_tag_set': 'when a tag is added',
    'on_user_set': 'when someone is assigned', 'on_archive': 'when a record is archived',
    'on_unarchive': 'when a record is restored', 'on_message_received': 'when a message arrives',
    'on_message_sent': 'when a message is sent', 'on_webhook': 'when another system calls in',
}


def _lower_first(text):
    text = str(text or '').strip()
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


class WorkflowContract(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ------------------------------------------------------------ contract
    def _contract(self, model, record=None):
        """The module's contract, normalised; discovered when none is declared."""
        result = {'source': 'none', 'model': model or '', 'label': '', 'area': '', 'stage_field': '',
                  'stages': [], 'effects': [], 'has_subject': False, 'submits_itself': False,
                  'approval_outcomes': {}, 'screen': '', 'own_stage_rows': False,
                  'safe_fields': [], 'adds_stages': False}
        if not model or model not in self.env:
            return result
        obj = self.env[model]
        declared = self._declared(model)
        label = str(declared.get('label') or obj._description or '')
        result.update(label=label, area=str(declared.get('area') or label),
                      stage_field=declared.get('stage_field') or '',
                      effects=[dict(e) for e in declared.get('effects', [])],
                      has_subject=hasattr(obj, '_workflow_subject'),
                      submits_itself=bool(declared.get('submits_itself')),
                      approval_outcomes=dict(declared.get('approval_outcomes') or {}),
                      screen=declared.get('screen') or '',
                      own_stage_rows=bool(declared.get('own_stage_rows')),
                      # WF2 P3b: values a workflow may set, and whether the
                      # area adds a stage itself (Hiring, D10).
                      safe_fields=[dict(f) for f in declared.get('safe_fields', []) if isinstance(f, dict) and f.get('key')],
                      adds_stages=bool(declared.get('adds_stages')))
        if hasattr(obj, '_workflow_stage_options'):
            stages, result['source'] = obj._workflow_stage_options(record), 'declared'
        elif declared.get('stages'):
            stages, result['source'] = declared['stages'], 'declared'
        else:
            result['source'] = 'discovered'
            tracks = self._record_stages(model, record)
            track = next((t for t in tracks if t['field'] == 'state'), None) or (tracks[0] if tracks else None)
            if not track:
                return result
            result['stage_field'] = track['field']
            stages = [dict({'key': o['key'], 'name': o['name']}, **({'id': o['key']} if track['type'] == 'many2one' else {}))
                      for o in track['options']]
        spec = obj._chain_spec() if hasattr(obj, '_chain_spec') else None
        submit = spec.get('submit_state') if spec and spec.get('state_field', 'state') == result['stage_field'] else None
        rows = []
        for s in stages:
            row = {'key': s['key'], 'name': str(s.get('name') or s['key']), 'enters': str(s.get('enters') or ''),
                   'exit': bool(s.get('exit')), 'optional': bool(s.get('optional')),
                   'approval': bool(s.get('approval')) or (submit is not None and str(s['key']) == str(submit)),
                   'renamable': bool(s.get('renamable')), 'kind': 'core', 'locked': True}
            row.update({k: s[k] for k in ('id', 'family', 'revision', 'meaning') if k in s})
            rows.append(row)
        result['stages'] = [r for r in rows if not r['exit']] + [r for r in rows if r['exit']]
        return result

    @api.model
    def metadata(self, model='', workflow_id=None):
        result = super().metadata(model, workflow_id)
        contract = self._contract(model)
        result['contract'] = {k: contract[k] for k in (
            'source', 'label', 'area', 'stage_field', 'has_subject', 'submits_itself', 'stages', 'screen',
            'own_stage_rows', 'adds_stages')}
        try:
            result['stage_catalogue'] = self.stage_catalogue(model, workflow_id) if (model or workflow_id) else None
        except (AccessError, UserError):
            result['stage_catalogue'] = None
        return result

    # ----------------------------------------------------- already happens
    @api.model
    def existing_behaviour(self, model='', workflow_id=None):
        """Everything that already happens for this kind of record, per stage."""
        self._design()
        if model and model not in {r['key'] for r in self._models()}:
            raise AccessError(_('This record type is not available.'))
        w = self._workflow(workflow_id) if workflow_id else None
        return self._existing(model, self._company(), exclude=w)

    def _existing(self, model, company, exclude=None):
        if not model:
            return []
        contract = self._contract(model)
        out = []

        def add(source, e):
            settings = dict(e['settings']) if isinstance(e.get('settings'), dict) else None
            if settings and settings.get('action') and not self.env.ref(settings['action'], raise_if_not_found=False):
                settings = None
            row = {'stage': e.get('stage'), 'kind': e.get('kind') or 'change', 'audience': e.get('audience') or 'other',
                   'text': str(e.get('text') or ''), 'owner': str(e.get('owner') or contract['area']),
                   'settings': settings, 'source': source}
            row.update({k: e[k] for k in ('detail', 'ref') if e.get(k)})
            out.append(row)
        for e in contract['effects']:
            add('area', e)
        obj = self.env[model]
        if hasattr(obj, '_workflow_effects'):
            for e in obj._workflow_effects(company) or []:
                add('area', e)
        for e in self._approval_effects(model, company, contract):
            add('approvals', e)
        rules = self.env['base.automation'].sudo().search([
            ('model_id.model', '=', model), ('active', '=', True)]) - self._studio_rules()
        for rule in rules:
            when = TRIGGER_WORDS.get(rule.trigger)
            add('rules', {'stage': None, 'kind': 'change', 'audience': 'other', 'owner': _('Automated rules'),
                          'text': _('“%(name)s” runs %(when)s.', name=rule.name, when=_(when)) if when
                          else _('“%s” runs automatically.', rule.name), 'ref': 'rule:%s' % rule.id})
        others = self.env['pb.workflow'].sudo().search([
            ('company_id', '=', company.id), ('source_model', '=', model), ('enabled', '=', True),
            ('published_id', '!=', False)] + ([('id', '!=', exclude.id)] if exclude else []))
        for other in others:
            d = other.published_id.definition
            binds = {i: self._bind_key(s) for i, s in enumerate(d.get('stages', []))}
            for n in d.get('nodes', []):
                at = binds.get(n.get('stage'))
                if n.get('type') == 'email':
                    template = self.env['mail.template'].sudo().browse(n.get('template_id') or 0).exists()
                    add('workflow', {'stage': at, 'kind': 'message', 'audience': n.get('audience') or 'other',
                                     'owner': other.name, 'settings': {'workflow_id': other.id},
                                     'text': _('“%(w)s” sends “%(t)s”.', w=other.name, t=template.name or n.get('title', ''))})
                elif n.get('type') in D.PEOPLE:
                    owner = n.get('owner') or {}
                    add('workflow', {'stage': at, 'kind': 'todo', 'audience': self._owner_audience(owner),
                                     'owner': other.name, 'settings': {'workflow_id': other.id},
                                     'text': _('“%(w)s” gives %(who)s a task: “%(t)s”.', w=other.name,
                                               who=_lower_first(self._owner_words(model, owner)), t=n.get('title', ''))})
                else:
                    row = self._other_step_row(model, other, n)
                    if row:
                        add('workflow', dict(row, stage=at, owner=other.name, settings={'workflow_id': other.id}))
        return out

    def _other_step_row(self, model, other, n):
        """Another workflow's WF2 P3b step as an "already happens" row
        (`ref` lets a double-up check match it exactly)."""
        kind = n.get('type')
        if kind == 'notify':
            owner = n.get('owner') or {}
            return {'kind': 'message', 'audience': self._owner_audience(owner), 'ref': 'notify',
                    'text': _('“%(w)s” tells %(who)s in the app: “%(t)s”.', w=other.name,
                              who=_lower_first(self._owner_words(model, owner)), t=n.get('title', ''))}
        if kind == 'update':
            spec = self._safe_spec(model, n.get('field')) or {}
            return {'kind': 'change', 'audience': 'other', 'ref': 'update:%s' % n.get('field'),
                    'text': _('“%(w)s” sets %(f)s.', w=other.name, f=spec.get('label') or n.get('field'))}
        if kind == 'create':
            creator = self._creator(n.get('creator')) or {}
            return {'kind': 'record', 'audience': 'other', 'ref': 'create:%s:%s' % (n.get('creator'), n.get('template_id')),
                    'text': _('“%(w)s” makes a draft: “%(t)s”.', w=other.name, t=n.get('title', ''))
                    if creator else ''}
        if kind == 'start':
            target = self.env['pb.workflow'].sudo().browse(int(n.get('workflow_id') or 0)).exists()
            return {'kind': 'change', 'audience': 'other', 'ref': 'start:%s' % n.get('workflow_id'),
                    'text': _('“%(w)s” hands over to “%(t)s”.', w=other.name, t=target.name or n.get('title', ''))}
        if kind == 'stage_move':
            stage = self.env['pb.workflow.stage'].sudo().browse(int((n.get('target') or {}).get('id') or 0)).exists()
            return {'kind': 'change', 'audience': 'other', 'ref': 'stage:%s' % ((n.get('target') or {}).get('id')),
                    'text': _('“%(w)s” moves it to %(s)s.', w=other.name, s=stage.name or n.get('title', ''))}
        return None

    def _owner_audience(self, owner):
        return {'manager': 'manager', 'managers_manager': 'manager',
                'subject': 'requester'}.get((owner or {}).get('kind'), 'other')

    def _bind_key(self, section):
        """The stage a section waits for, as an effect `stage` value."""
        bind = section.get('bind') if isinstance(section, dict) else None
        if not isinstance(bind, dict):
            return None
        if bind.get('kind') == 'core':
            return bind.get('value')
        if bind.get('kind') == 'yours' and type(bind.get('id')) is int:
            return 'yours:%s' % bind['id']
        return None

    def _approval_process_of(self, model):
        Process = self.env['biz.approval.process'].sudo()
        key = getattr(self.env[model], '_approval_process_key', None)
        process = Process._by_key(key) if key else Process.search([('model_name', '=', model)], limit=1)
        return process if process and process.connected else Process

    def _approval_effects(self, model, company, contract):
        """What the approval engine already does here, read from the engine."""
        process = self._approval_process_of(model)
        if not process:
            return []
        at = next((s['key'] for s in contract['stages'] if s.get('approval')), None)
        base = {'stage': at, 'owner': _('Approval Matrix'), 'settings': {'action': MATRIX_ACTION}}
        engine = self.env['biz.approval.engine'].sudo()
        found = engine.resolve_binding(company.id, process.key, [''], 'any')
        problem = found.get('error') or {}
        if problem.get('code') in ('no_route', 'no_version'):
            partial = problem['code'] == 'no_route' and self.env['biz.approval.binding'].sudo().search_count([
                ('company_id', '=', company.id), ('process_id', '=', process.id), ('active', '=', True)])
            return [dict(base, kind='change', audience='approver',
                         text=_('Approval routes are set up for some parts of the business only. Approval Matrix shows which.')
                         if partial else _('No approval route is set up for this yet.'))]
        if problem.get('code') == 'paused':
            return [dict(base, kind='change', audience='approver',
                         text=_('Approvals for this are paused in Approval Matrix, so nothing new can be sent in.'))]
        if problem:
            return [dict(base, kind='change', audience='approver', text=str(problem.get('message') or ''))]
        version = self.env['biz.approval.workflow.version'].sudo().browse(found['version_id'])
        labels = engine.route_labels(version.definition)
        route = dict(base, kind='change', audience='approver',
                     text=_('Approval route “%(name)s”: %(route)s.', name=found['workflow_name'],
                            route=_(', then ').join(labels) or _('no steps yet')),
                     detail=engine.summary(version.definition))
        decisions = AD.decision_steps(AD.normalise(version.definition))
        if decisions and all(s['kind'] == 'fast' for s in decisions):
            # The "No approval needed" lane: nobody is asked, told or
            # reminded, so only the route itself is listed (WF2 P3a).
            return [route]
        effects = [route,
                   dict(base, kind='message', audience='approver',
                        text=_('Each approver is told when it is their turn and gets a to-do.')),
                   dict(base, kind='reminder', audience='approver',
                        text=_('A late approver is reminded, and then it is passed up.'))]
        outcomes = self._approval_outcomes(model, contract)
        note = _('People who only use the employee home are not told this way.')
        for key, text in (('approved', _('The person who sent it in is told it is approved.')),
                          ('returned', _('The person who sent it in is told it was sent back.')),
                          ('rejected', _('The person who sent it in is told it was turned down.'))):
            effects.append(dict(base, stage=outcomes.get(key), kind='message', audience='requester',
                                text=text, detail=note))
        return effects

    def _approval_outcomes(self, model, contract):
        """Which stage each engine outcome lands on, as the area says or as
        the chain declares."""
        found = dict(contract.get('approval_outcomes') or {})
        obj = self.env[model]
        spec = obj._chain_spec() if hasattr(obj, '_chain_spec') else None
        if 'approved' not in found and spec and spec.get('driven'):
            found['approved'] = list(spec['driven'])[-1]
        if 'rejected' not in found:
            found['rejected'] = next((s['key'] for s in contract['stages'] if s.get('exit')), None)
        return found

    # --------------------------------------------------------- validation
    def _activity_types(self):
        return self.env['mail.activity.type'].search([
            ('res_model', 'in', [False, 'pb.workflow.run']), ('category', '=', 'default')])

    def _validate(self, w, definition):
        issues = super()._validate(w, definition)
        if any(i.get('code') in D.STRUCTURAL for i in issues) or not isinstance(definition, dict):
            return issues
        try:
            binding = self._binding_issues(w, definition)
            issues += binding + self._same_path_templates(definition)
            if not binding:
                issues += self._repeat_warnings(w, definition)
            issues += self._send_back_warnings(definition) + self._same_path_creates(definition)
        except (KeyError, TypeError, AttributeError, IndexError, ValueError):
            pass
        return issues

    def _positions(self, w):
        """Catalogue order for a workflow's model: {('core', key)|('yours', id): index}, exits."""
        model = w.source_model or ''
        contract = self._contract(model)
        stages = self._user_stages(model, self.env['pb.workflow'] if model else w, w.company_id)
        positions, exits = {}, {}
        for i, (kind, item) in enumerate(self._merged(contract, stages)):
            if kind == 'core' and item.get('exit'):
                exits[str(item['key'])] = item['name']
            elif kind == 'core':
                positions[('core', str(item['key']))] = i
            else:
                positions[('yours', item.id)] = i
        return positions, exits

    def _binding_issues(self, w, d):
        sections = [(i, s) for i, s in enumerate(d['stages']) if isinstance(s, dict) and s.get('bind')]
        if not sections:
            return []
        positions, exits = self._positions(w)
        out, seen, last = [], set(), -1

        def error(i, code, text):
            out.append({'id': 'sections', 'section': i, 'code': code, 'text': text, 'severity': 'error'})
        for i, s in sections:
            bind, name = s['bind'], s.get('name', '')
            ident = None
            if isinstance(bind, dict) and bind.get('kind') == 'core' and w.source_model:
                value = str(bind.get('value'))
                if value in exits:
                    error(i, 'bind_exit', _('Section “%(s)s” cannot wait for %(e)s: records that get there stop.', s=name, e=exits[value]))
                    continue
                ident = ('core', value)
            elif isinstance(bind, dict) and bind.get('kind') == 'yours' and type(bind.get('id')) is int:
                ident = ('yours', bind['id'])
            if ident not in positions:
                error(i, 'bind_unknown', _('Section “%s” waits for a stage that does not exist any more. Choose another stage, or make it a heading.', name))
                continue
            if ident in seen:
                error(i, 'bind_duplicate', _('Section “%s” waits for a stage another section already uses. Each stage can start one section.', name))
                continue
            if positions[ident] <= last:
                error(i, 'bind_order', _('Linked sections follow the stage order. Move section “%s” or choose a later stage.', name))
            seen.add(ident)
            last = max(last, positions[ident])
        return out

    def _same_path_templates(self, d):
        """The same message twice is an error only when both can run."""
        parent = {}
        for n in d['nodes']:
            for b in n.get('branches', []):
                for child in b.get('steps', []):
                    parent[child] = (n['id'], b['id'] if n['type'] == 'branch' else None)
            if n['type'] == 'subprocess':
                for child in n.get('steps', []):
                    parent[child] = (n['id'], None)

        def paths(key):
            chosen, guard = {}, 0
            while key in parent and guard < 50:
                group, branch = parent[key]
                if branch:
                    chosen[group] = branch
                key, guard = group, guard + 1
            return chosen
        emails = [n for n in d['nodes'] if n['type'] == 'email' and type(n.get('template_id')) is int]
        out, flagged = [], set()
        for i, a in enumerate(emails):
            for b in emails[i + 1:]:
                if a['template_id'] != b['template_id'] or b['id'] in flagged:
                    continue
                pa, pb = paths(a['id']), paths(b['id'])
                if not any(g in pb and pb[g] != pa[g] for g in pa):
                    flagged.add(b['id'])
                    out.append({'id': b['id'], 'code': 'duplicate_email', 'severity': 'error',
                                'text': _('This message is already sent by another step on the same path.')})
        return out

    def _send_back_warnings(self, d):
        """A send back over a message or a notice sends it again (WF2 P3b).
        Errors (an approval or a change in between) are D's; this is the
        warning the designer keeps on purpose."""
        out, nodes, parent_map = [], {n['id']: n for n in d['nodes']}, D.parents(d)
        for n in d['nodes']:
            if n['type'] != 'send_back' or n.get('target') not in d['order']:
                continue
            again = [nodes[x]['title'] for x in D.between(d, n['target'], n['id'], parent_map)
                     if nodes[x]['type'] in D.TELLS]
            if again:
                out.append({'id': n['id'], 'code': 'send_back_repeats', 'severity': 'warning',
                            'acknowledged': bool(n.get('ack_repeat')), 'existing': '', 'existing_source': 'workflow',
                            'text': _('Going back sends these again: %s.', ', '.join(again))})
        return out

    def _same_path_creates(self, d):
        """The same draft made twice on one path is an error, like the same
        email twice (`_same_path_templates`)."""
        made = [n for n in d['nodes'] if n['type'] == 'create' and n.get('creator') and type(n.get('template_id')) is int]
        if len(made) < 2:
            return []
        parent_map = D.parents(d)
        def chosen(key):
            out, at, guard = {}, key, 0
            while at in parent_map and guard < 50:
                group, branch = parent_map[at]
                if branch and group['type'] == 'branch':
                    out[group['id']] = branch
                at, guard = group['id'], guard + 1
            return out
        out, flagged = [], set()
        for i, a in enumerate(made):
            for b in made[i + 1:]:
                if (a['creator'], a['template_id']) != (b['creator'], b['template_id']) or b['id'] in flagged:
                    continue
                pa, pb = chosen(a['id']), chosen(b['id'])
                if not any(g in pb and pb[g] != pa[g] for g in pa):
                    flagged.add(b['id'])
                    out.append({'id': b['id'], 'code': 'duplicate_create', 'severity': 'error',
                                'text': _('Another step on the same path already makes this draft.')})
        return out

    def _repeat_warnings(self, w, d):
        model = w.source_model
        if not model or not any(n['type'] in ('email', 'task', 'input', 'matrix', 'confirm', 'notify', 'update',
                                               'create', 'start', 'stage_move') for n in d['nodes']):
            return []
        contract = self._contract(model)
        effects = self._existing(model, w.company_id, exclude=w if w.id else None)
        binds = {i: self._bind_key(s) for i, s in enumerate(d['stages'])}
        out = []

        def warn(n, effect, text):
            out.append({'id': n['id'], 'code': 'repeats_existing', 'severity': 'warning', 'text': text,
                        'acknowledged': bool(n.get('ack_repeat')), 'existing': effect.get('text', ''),
                        'existing_source': effect.get('source', '')})
        for n in d['nodes']:
            at = binds.get(n.get('stage'))
            if n['type'] == 'email' and at is not None:
                audience = n.get('audience')
                hit = next((e for e in effects if e['kind'] == 'message' and str(e['stage']) == str(at)
                            and (not audience or e['audience'] == audience)), None)
                if hit:
                    warn(n, hit, _('%(owner)s already does this here: %(text)s This step would send a second message.',
                                   owner=hit['owner'], text=_lower_first(hit['text'])))
            elif n['type'] == 'notify' and at is not None:
                audience = self._owner_audience(n.get('owner'))
                hit = next((e for e in effects if e['kind'] == 'message' and str(e['stage']) == str(at)
                            and audience != 'other' and e['audience'] == audience), None)
                if hit:
                    warn(n, hit, _('%(owner)s already does this here: %(text)s This step would tell them a second time.',
                                   owner=hit['owner'], text=_lower_first(hit['text'])))
            elif n['type'] in ('update', 'create', 'start', 'stage_move'):
                ref = {'update': 'update:%s' % n.get('field'),
                       'create': 'create:%s:%s' % (n.get('creator'), n.get('template_id')),
                       'start': 'start:%s' % n.get('workflow_id'),
                       'stage_move': 'stage:%s' % ((n.get('target') or {}).get('id'))}[n['type']]
                hit = next((e for e in effects if e.get('ref') == ref and e['source'] == 'workflow'), None)
                if hit:
                    warn(n, hit, _('Another workflow already does this: %(text)s This step would do it a second time.',
                                   text=_lower_first(hit['text'])))
                elif n['type'] == 'stage_move':
                    stage = self.env['pb.workflow.stage'].sudo().browse(int((n.get('target') or {}).get('id') or 0)).exists()
                    if stage and stage.enter in ('auto', 'rule'):
                        warn(n, {'text': '', 'source': 'workflow'},
                             _('“%s” already gets records by itself. This step would move them there a second way.', stage.name))
            elif n['type'] in D.PEOPLE and at is not None:
                audience = self._owner_audience(n.get('owner'))
                wanted = {'manager', 'approver'} if audience == 'manager' else {audience} if audience != 'other' else set()
                hit = next((e for e in effects if e['kind'] == 'todo' and str(e['stage']) == str(at)
                            and e['audience'] in wanted), None)
                if hit:
                    warn(n, hit, _('%(owner)s already does this here: %(text)s This step would give them a second task.',
                                   owner=hit['owner'], text=_lower_first(hit['text'])))
            elif n['type'] == 'matrix' and n.get('mode', 'submit') == 'submit' and contract['submits_itself']:
                warn(n, {'text': '', 'source': 'area'},
                     _('%s already sends each one for approval by itself. This step would send it again. '
                       'Choose “Wait for the approval this record already goes through” instead.', contract['area']))
        return out
