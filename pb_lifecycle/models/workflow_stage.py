"""User-made stages beside a module's own statuses (WF2 P2, owner ruling R4).

A business area owns its record's status (Draft → Waiting approval → …).
People still want to say "Payment scheduled" or "Ready for the board" without
programming. A user-made stage sits AFTER one of the module's statuses and
counts as it (`anchor_value`); the record's position in it is stored here,
beside the record, and never in the record's own status field (R2c).

Invariant: a position row is valid only while the record's module status
equals its stage's anchor. `_record_position` enforces it lazily and removes a
stale row the first time anyone looks.
"""
import json

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from . import workflow_definition as D
from .workflow_models import internal, system

ENTER = [('auto', 'By itself'), ('person', 'A person moves it'), ('rule', 'When a rule matches')]
OWNER_KINDS = ('initiator', 'user', 'role', 'manager', 'field', 'subject')
RUN = 'pb.workflow.run'


class WorkflowStage(models.Model):
    _name = 'pb.workflow.stage'
    _description = 'Workflow stage'
    _inherit = ['pb.workflow.protected']
    _order = 'sequence, id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    source_model = fields.Char(index=True)
    workflow_id = fields.Many2one('pb.workflow', ondelete='cascade', index=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    anchor_value = fields.Char()
    enter = fields.Selection(ENTER, required=True, default='auto')
    enter_owner = fields.Json(default=dict)
    enter_rule = fields.Json(default=dict)
    target_hours = fields.Integer(default=0)
    active = fields.Boolean(default=True)

    @api.constrains('name', 'company_id', 'source_model', 'workflow_id', 'active')
    def _check_unique_name(self):
        for rec in self.filtered('active'):
            same = self.sudo().search_count([
                ('id', '!=', rec.id), ('company_id', '=', rec.company_id.id),
                ('source_model', '=', rec.source_model or False),
                ('workflow_id', '=', rec.workflow_id.id or False),
                ('name', '=ilike', rec.name)])
            if same:
                raise ValidationError(_('There is already a stage called “%s”.', rec.name))


class WorkflowRecordStage(models.Model):
    _name = 'pb.workflow.record.stage'
    _description = 'Record position in a workflow stage'
    _inherit = ['pb.workflow.protected']
    _order = 'id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    stage_id = fields.Many2one('pb.workflow.stage', required=True, ondelete='restrict', index=True)
    entered_at = fields.Datetime(default=fields.Datetime.now, required=True)
    entered_by = fields.Many2one('res.users')
    run_id = fields.Many2one('pb.workflow.run', ondelete='set null')
    _unique_position = models.Constraint('unique(company_id, res_model, res_id)',
                                         'A record is in one workflow stage at a time.')

    def _check_access(self, operation):
        """Reading a record's position needs read access to the record."""
        result = super()._check_access(operation)
        if result or self.env.su:
            return result
        studio = self.env['pb.workflow.studio']
        for row in self.sudo():
            try:
                if row.res_model == RUN:
                    studio.with_company(row.company_id)._run(row.res_id)
                else:
                    studio.with_company(row.company_id)._source(row.res_model, row.res_id)
            except (AccessError, UserError):
                return self, lambda: AccessError(_('You do not have access to this record.'))
        return None

    def _read_format(self, fnames, load='_classic_read'):
        if not self.env.su:
            self.check_access('read')
        return super()._read_format(fnames, load)


class WorkflowStageService(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    # ------------------------------------------------------------ helpers
    def _stage_scope(self, model, workflow_id=None):
        """(model, workflow) a stage list belongs to: a record type, or one
        new-process workflow."""
        if model:
            if model not in {r['key'] for r in self._models()}:
                raise AccessError(_('This record type is not available.'))
            return model, self.env['pb.workflow']
        if not workflow_id:
            raise UserError(_('Choose the workflow these stages belong to.'))
        w = self._workflow(workflow_id)
        if w.source_model:
            raise UserError(_('This workflow follows a record. Its stages belong to that kind of record.'))
        return '', w

    def _user_stages(self, model, workflow, company=None):
        domain = [('company_id', '=', (company or self.env.company).id)]
        if model:
            domain += [('source_model', '=', model), ('workflow_id', '=', False)]
        else:
            domain += [('workflow_id', '=', workflow.id)]
        return self.env['pb.workflow.stage'].sudo().search(domain)

    def _stage(self, stage_id):
        self._design()
        stage = self.env['pb.workflow.stage'].sudo().browse(int(stage_id or 0)).exists()
        if not stage or not stage.active or stage.company_id != self.env.company:
            raise AccessError(_('This stage is not available in your current company.'))
        return stage

    def _merged(self, contract, stages):
        """Module stages in their order, each user-made stage after its
        anchor (in sequence order), exits last."""
        rows = []
        later = {}
        for s in stages:
            later.setdefault(str(s.anchor_value or ''), []).append(s)
        for s in later.get('', []):
            rows.append(('yours', s))
        for core in contract['stages']:
            if core.get('exit'):
                continue
            rows.append(('core', core))
            for s in later.get(str(core['key']), []):
                rows.append(('yours', s))
        rows += [('core', core) for core in contract['stages'] if core.get('exit')]
        return rows

    def _owner_words(self, model, owner):
        owner = owner or {}
        kind = owner.get('kind')
        if kind == 'user':
            person = self.env['res.users'].sudo().browse(int(owner.get('id') or 0)).exists()
            return person.name if person else _('A named person')
        if kind == 'role':
            role = self.env['biz.approval.role'].sudo().browse(int(owner.get('id') or 0)).exists()
            return role.name if role else _('A responsibility')
        if kind == 'field':
            label = next((f['label'] for f in self._source_fields(model) if f['key'] == owner.get('field')), '')
            return label or _('A person on this record')
        return {'manager': _('Their manager'), 'subject': _('The person this is about'),
                'initiator': _('The person who started the workflow')}.get(kind, _('Someone'))

    def _enters_words(self, model, stage):
        if stage.enter == 'person':
            return _('%(who)s presses Move to %(stage)s', who=self._owner_words(model, stage.enter_owner), stage=stage.name)
        if stage.enter == 'rule':
            words = self._rule_words(model, stage.enter_rule)
            return _('By itself, when %s', words) if words else _('By itself, when its rule matches')
        return _('By itself, when the steps before are finished')

    def _check_rule(self, model, company, rule):
        """The existing condition validator, applied to one rule."""
        d = D.fresh('Stage rule')
        d['nodes'].append({'id': 'rule', 'type': 'wait', 'title': 'Rule', 'stage': 0, 'hours': 1, 'wait_for': rule})
        d['order'].append('rule')
        probe = self.env['pb.workflow'].new({'name': 'Stage rule', 'company_id': company.id,
                                             'source_model': model or False})
        errors = [i for i in self._validate(probe, d) if i.get('severity') != 'warning']
        if errors:
            raise UserError(errors[0]['text'])

    def _check_owner(self, model, company, owner):
        if not isinstance(owner, dict) or owner.get('kind') not in OWNER_KINDS:
            raise UserError(_('Choose who moves records into this stage.'))
        kind = owner['kind']
        if kind == 'user':
            person = self.env['res.users'].sudo().browse(owner.get('id') if type(owner.get('id')) is int else 0).exists()
            if not person or not person.active or person.share or company not in person.company_ids:
                raise UserError(_('Choose an active person in this company.'))
        if kind == 'role':
            role = self.env['biz.approval.role'].sudo().browse(owner.get('id') if type(owner.get('id')) is int else 0).exists()
            if not role or role.is_pool:
                raise UserError(_('Choose an existing single-person responsibility.'))
        if kind == 'field':
            f = next((f for f in self._source_fields(model) if f['key'] == owner.get('field')), {})
            if not model or f.get('type') != 'many2one' or f.get('relation') != 'res.users':
                raise UserError(_('Choose a person field from this record.'))
        if kind in ('manager', 'subject') and not model:
            raise UserError(_('A new process has no record of its own. Choose a named person or a responsibility.'))
        if kind == 'subject' and not hasattr(self.env[model], '_workflow_subject'):
            raise UserError(_('This kind of record does not say who it is about. Choose someone else.'))
        return {k: owner[k] for k in ('kind', 'id', 'field') if k in owner}

    def _stage_values(self, model, company, contract, values, stage=None):
        if not isinstance(values, dict) or not D.safe_json(values, 50000):
            raise UserError(_('These stage settings are not valid.'))
        vals = {}
        if 'name' in values or stage is None:
            name = str(values.get('name') or '').strip()
            if not name or len(name) > 40:
                raise UserError(_('Give the stage a name of up to 40 characters.'))
            vals['name'] = name
        if 'anchor_value' in values or stage is None:
            anchor = values.get('anchor_value')
            if model:
                keys = {str(s['key']): s for s in contract['stages']}
                if str(anchor) not in keys or keys[str(anchor)].get('exit'):
                    raise UserError(_('Choose the existing stage this one comes after.'))
                vals['anchor_value'] = str(anchor)
            elif anchor:
                raise UserError(_('A new process has no existing stages to follow.'))
            else:
                vals['anchor_value'] = False
        enter = values.get('enter', stage.enter if stage else 'auto')
        if enter not in dict(ENTER):
            raise UserError(_('Choose how records get into this stage.'))
        vals['enter'] = enter
        if enter == 'person':
            vals['enter_owner'] = self._check_owner(model, company, values.get('enter_owner', stage.enter_owner if stage else None))
        elif 'enter' in values or stage is None:
            vals['enter_owner'] = {}
        if enter == 'rule':
            rule = values.get('enter_rule', stage.enter_rule if stage else None)
            if not isinstance(rule, dict) or not rule.get('rules'):
                raise UserError(_('Add the rule that moves records into this stage.'))
            self._check_rule(model, company, rule)
            vals['enter_rule'] = rule
        elif 'enter' in values or stage is None:
            vals['enter_rule'] = {}
        if 'target_hours' in values:
            hours = values['target_hours']
            if type(hours) is not int or not 0 <= hours <= 8760:
                raise UserError(_('Use a target from 0 to 8,760 hours.'))
            vals['target_hours'] = hours
        return vals

    def _occupants(self, stage):
        """Valid positions in one user-made stage (stale rows are removed).

        Batched: one contract and one read of the records per stage, not one
        per row (a stage can hold hundreds of records)."""
        sysenv = system(self.env, stage.company_id)
        rows = sysenv['pb.workflow.record.stage'].search([('stage_id', '=', stage.id)])
        if not rows:
            return self.env['pb.workflow.record.stage']
        model = stage.source_model or RUN
        if model == RUN:
            alive = set(sysenv[RUN].browse(rows.mapped('res_id')).exists().ids)
            valid = rows.filtered(lambda r: r.res_id in alive)
        elif model not in sysenv:
            valid = rows.browse()
        else:
            contract = sysenv['pb.workflow.studio']._contract(model)
            records = {r.id: r for r in sysenv[model].browse(rows.mapped('res_id')).exists()}
            valid = rows.filtered(lambda r: r.res_id in records and
                                  str(self._status_value(contract, records[r.res_id])) == str(stage.anchor_value))
        for stale in rows - valid:
            if stale.run_id:
                self._stage_log(stale.run_id, _('Left %s: the record moved on.', stage.name))
            stale.unlink()
        return self.env['pb.workflow.record.stage'].sudo().browse(valid.ids)

    def _binding_workflows(self, stage):
        """Enabled workflows whose published version waits on this stage."""
        found = self.env['pb.workflow']
        for w in self.env['pb.workflow'].sudo().search([
                ('company_id', '=', stage.company_id.id), ('enabled', '=', True), ('published_id', '!=', False)]):
            for s in w.published_id.definition.get('stages', []):
                bind = s.get('bind') if isinstance(s, dict) else None
                if isinstance(bind, dict) and bind.get('kind') == 'yours' and bind.get('id') == stage.id:
                    found |= w
        return found

    # --------------------------------------------------------- positions
    def _status_value(self, contract, record):
        """The record's module status as a contract key, or None."""
        field = contract.get('stage_field')
        if record is None or not field or field not in record._fields:
            return None
        value = record.sudo()[field]
        if record._fields[field].type == 'many2one':
            if not value:
                return None
            return next((s['key'] for s in contract['stages'] if s.get('id') == value.id), value.id)
        return value or None

    def _record_position(self, model, res_id, company=None):
        """The record's valid position row, or an empty recordset.

        A row whose stage no longer matches the record's module status is
        removed here (system account, noted in the run's history)."""
        company = company or self.env.company
        sysenv = system(self.env, company)
        Pos = sysenv['pb.workflow.record.stage']
        row = Pos.search([('company_id', '=', company.id), ('res_model', '=', model),
                          ('res_id', '=', int(res_id or 0))], limit=1)
        if not row:
            return self.env['pb.workflow.record.stage']
        stage = row.stage_id
        valid = stage.active
        if valid and model != RUN:
            record = sysenv[model].browse(row.res_id).exists() if model in sysenv else None
            if not record:
                valid = False
            else:
                contract = sysenv['pb.workflow.studio']._contract(model, record)
                valid = str(self._status_value(contract, record)) == str(stage.anchor_value)
        elif valid and model == RUN:
            valid = bool(sysenv[RUN].browse(row.res_id).exists())
        if valid:
            return self.env['pb.workflow.record.stage'].sudo().browse(row.id)
        run = row.run_id
        if run:
            self._stage_log(run, _('Left %s: the record moved on.', stage.name), stage=None)
        row.unlink()
        return self.env['pb.workflow.record.stage']

    def _stage_log(self, run, text, stage=None, actor=None):
        internal(self.env['pb.workflow.log']).create({
            'run_id': run.id, 'company_id': run.company_id.id, 'message': text[:500],
            'actor_id': (actor or self.env['res.users'].browse(SUPERUSER_ID)).id,
            'stage_id': stage.id if stage else False})

    def _set_position(self, model, res_id, stage, company, run=None, mover=None):
        """Put a record into a user-made stage. Never touches the record.

        No local may be called `user` or `uid` in a method that calls `_()`:
        the translation lookup reads them to guess a language (ledger G12)."""
        sysenv = system(self.env, company)
        Pos = sysenv['pb.workflow.record.stage']
        old = self._record_position(model, res_id, company)
        if old and old.stage_id == stage:
            return old
        actor = mover or sysenv['res.users'].browse(SUPERUSER_ID)
        vals = {'stage_id': stage.id, 'entered_at': fields.Datetime.now(),
                'entered_by': actor.id, 'run_id': run.id if run else False}
        row = Pos.search([('company_id', '=', company.id), ('res_model', '=', model), ('res_id', '=', int(res_id))], limit=1)
        if row:
            internal(row).write(vals)
        else:
            row = internal(Pos).create(dict(vals, company_id=company.id, res_model=model, res_id=int(res_id)))
        runs = sysenv[RUN].search([('company_id', '=', company.id), ('state', 'in', ['running', 'waiting', 'failed']),
                                   ('source_model', '=', model), ('source_id', '=', int(res_id))]) if model != RUN \
            else sysenv[RUN].browse(int(res_id))
        for target in (runs | (run.sudo() if run else sysenv[RUN])):
            if old:
                self._stage_log(target, _('Left %s.', old.stage_id.name), actor=actor)
            text = _('Moved to %(stage)s by %(who)s.', stage=stage.name, who=actor.name) if mover else \
                _('Moved to %s.', stage.name)
            self._stage_log(target, text, stage=stage, actor=actor)
        return self.env['pb.workflow.record.stage'].sudo().browse(row.id)

    # ------------------------------------------------------------- gates
    def _gate(self, run, index, definition):
        """('pass'|'wait'|'closed'|'problem', words) for one bound section.

        Private: called by the run loop in the system environment."""
        run = run.sudo()
        bind = definition['stages'][index].get('bind') or {}
        company = run.company_id
        if run.source_model:
            source = run._source()
            contract = self._contract(run.source_model, source)
            order = [s for s in contract['stages'] if not s.get('exit')]
            keys = [str(s['key']) for s in order]
            status = str(self._status_value(contract, source))
            exit_ = next((s for s in contract['stages'] if s.get('exit') and str(s['key']) == status), None)
            if exit_:
                return 'closed', exit_['name']

            def reached(value):
                return status in keys and str(value) in keys and keys.index(status) >= keys.index(str(value))
            if bind.get('kind') == 'core':
                target = next((s for s in order if str(s['key']) == str(bind.get('value'))), None)
                if not target:
                    return 'problem', _('This workflow waits for a stage that no longer exists. Edit its sections.')
                return ('pass', '') if reached(target['key']) else ('wait', _('Waiting for this to reach %s.', target['name']))
            model, res_id = run.source_model, run.source_id
        else:
            source, contract, model, res_id = run, None, RUN, run.id
        stage = self.env['pb.workflow.stage'].sudo().browse(int(bind.get('id') or 0)).exists()
        if not stage or stage.company_id != company:
            return 'problem', _('This workflow waits for a stage that no longer exists. Edit its sections.')
        if contract is not None and stage.anchor_value:
            anchor = next((s for s in order if str(s['key']) == stage.anchor_value), None)
            if not anchor:
                return 'problem', _('“%s” follows a stage that no longer exists.', stage.name)
            if not reached(anchor['key']):
                return 'wait', _('Waiting for this to reach %s.', anchor['name'])
            if status != stage.anchor_value:
                # The record went past this stage without anyone putting it
                # there; nothing is written, the work simply continues.
                return 'pass', ''
        current = self._record_position(model, res_id, company)
        if current and (current.stage_id == stage or (
                current.stage_id.anchor_value == stage.anchor_value and
                (current.stage_id.sequence, current.stage_id.id) > (stage.sequence, stage.id))):
            return 'pass', ''
        if stage.enter == 'auto':
            self._set_position(model, res_id, stage, company, run=run)
            return 'pass', ''
        if stage.enter == 'rule':
            if D.matches(stage.enter_rule, run._condition_values({'stage': index})):
                self._set_position(model, res_id, stage, company, run=run)
                return 'pass', ''
            words = self._rule_words(run.source_model, stage.enter_rule)
            return 'wait', (_('Waiting until %(rule)s, to move to %(stage)s.', rule=words, stage=stage.name)
                            if words else _('Waiting for its rule to move this to %s.', stage.name))
        who = self._owner_words(run.source_model, stage.enter_owner)
        try:
            owner_id = self._resolve_owner(run, stage.enter_owner or {})
            who = self.env['res.users'].sudo().browse(owner_id).name or who
        except (AccessError, UserError):
            pass
        return 'wait', _('Waiting for %(who)s to move this to %(stage)s.', who=who, stage=stage.name)

    # ------------------------------------------------------------ facade
    @api.model
    def stage_catalogue(self, model='', workflow_id=None, record_id=None):
        """Every stage a designer can use, in order: the module's own
        (locked) and the company's own, each after the stage it follows."""
        self._design()
        model, workflow = self._stage_scope(model, workflow_id)
        record = self._source(model, record_id) if model and record_id else None
        contract = self._contract(model, record)
        stages = self._user_stages(model, workflow)
        rows = []
        for kind, item in self._merged(contract, stages):
            if kind == 'core':
                rows.append({'id': 'core:%s' % item['key'], 'kind': 'core', 'key': item['key'],
                             'name': item['name'], 'locked': True, 'area': contract['area'],
                             'enters': item.get('enters', ''), 'exit': bool(item.get('exit')),
                             'approval': bool(item.get('approval')), 'renamable': bool(item.get('renamable')),
                             'revision': item.get('revision'), 'stage_id': item.get('id')})
                continue
            anchor = next((c for c in contract['stages'] if str(c['key']) == str(item.anchor_value)), {})
            rows.append({'id': 'yours:%s' % item.id, 'kind': 'yours', 'key': item.id, 'name': item.name,
                         'locked': False, 'counts_as': anchor.get('name', ''), 'anchor': item.anchor_value or '',
                         'enter': item.enter, 'enter_owner': item.enter_owner or {}, 'enter_rule': item.enter_rule or {},
                         'enters': self._enters_words(model, item), 'target_hours': item.target_hours,
                         'exit': False, 'count': len(self._occupants(item))})
        return {'model': model, 'workflow_id': workflow.id or None, 'source': contract['source'],
                'label': contract['label'], 'area': contract['area'], 'stages': rows}

    @api.model
    def stage_create(self, model='', workflow_id=None, values=None):
        self._design()
        model, workflow = self._stage_scope(model, workflow_id)
        company = self._company()
        contract = self._contract(model)
        vals = self._stage_values(model, company, contract, values or {})
        siblings = self._user_stages(model, workflow).filtered(
            lambda s: str(s.anchor_value or '') == str(vals.get('anchor_value') or ''))
        vals.update(company_id=company.id, source_model=model or False, workflow_id=workflow.id or False,
                    sequence=max(siblings.mapped('sequence') or [0]) + 10)
        internal(self.env['pb.workflow.stage']).create(vals)
        return self.stage_catalogue(model, workflow.id)

    @api.model
    def stage_update(self, stage_id, values=None):
        stage = self._stage(stage_id)
        model, workflow = stage.source_model or '', stage.workflow_id
        self._stage_scope(model, workflow.id)
        values = dict(values or {})
        if 'anchor_value' in values and str(values['anchor_value'] or '') != str(stage.anchor_value or ''):
            if self._occupants(stage):
                raise UserError(_('Records are in “%s” now. Move them on before it follows another stage.', stage.name))
        vals = self._stage_values(model, stage.company_id, self._contract(model), values, stage)
        internal(stage).write(vals)
        return self.stage_catalogue(model, workflow.id)

    @api.model
    def stage_reorder(self, model='', workflow_id=None, ordered=None):
        """`ordered`: the full list in its new order, module stages by their
        key (strings) and user-made stages by id (numbers). Each user-made
        stage then follows the nearest module stage before it."""
        self._design()
        model, workflow = self._stage_scope(model, workflow_id)
        contract = self._contract(model)
        stages = self._user_stages(model, workflow)
        core = [str(s['key']) for s in contract['stages'] if not s.get('exit')]
        if not isinstance(ordered, list) or len(ordered) > 400:
            raise UserError(_('This stage order is not valid.'))
        given_core = [str(x) for x in ordered if type(x) is not int]
        given_yours = [x for x in ordered if type(x) is int]
        if given_core != core or sorted(given_yours) != sorted(stages.ids):
            raise UserError(_('Keep every stage once, and the existing stages in their own order.'))
        if model and ordered and type(ordered[0]) is int:
            raise UserError(_('Your own stages come after one of the existing stages.'))
        anchor, plan = '', {}
        for position, item in enumerate(ordered):
            if type(item) is not int:
                anchor = str(item)
                continue
            plan[item] = (anchor if model else '', (position + 1) * 10)
        for stage in stages:
            new_anchor, sequence = plan[stage.id]
            if str(stage.anchor_value or '') != new_anchor and self._occupants(stage):
                raise UserError(_('Records are in “%s” now. Move them on before it follows another stage.', stage.name))
        for stage in stages:
            new_anchor, sequence = plan[stage.id]
            internal(stage).write({'anchor_value': new_anchor or False, 'sequence': sequence})
        return self.stage_catalogue(model, workflow.id)

    @api.model
    def stage_delete(self, stage_id):
        stage = self._stage(stage_id)
        model, workflow = stage.source_model or '', stage.workflow_id
        count = len(self._occupants(stage))
        if count:
            raise UserError(_('%(n)s records are in “%(stage)s” now. Move them on before removing it.', n=count, stage=stage.name)
                            if count > 1 else _('A record is in “%s” now. Move it on before removing it.', stage.name))
        users = self._binding_workflows(stage)
        if users:
            raise UserError(_('“%(w)s” waits for this stage. Pause that workflow or change its sections first.',
                              w=', '.join(users.mapped('name'))))
        internal(stage).write({'active': False})
        return self.stage_catalogue(model, workflow.id)

    @api.model
    def stage_rename_shared(self, model, stage_key, name, revision):
        """Rename one of the module's own stages, through the module."""
        self._design()
        if model not in {r['key'] for r in self._models()}:
            raise AccessError(_('This record type is not available.'))
        obj = self.env[model]
        if not hasattr(obj, '_workflow_rename_stage'):
            raise UserError(_('Manage these stages through the module that owns them.'))
        stage_id = stage_key if type(stage_key) is int else next(
            (s.get('id') for s in self._contract(model)['stages'] if str(s['key']) == str(stage_key)), None)
        if not stage_id:
            raise UserError(_('This stage no longer exists.'))
        obj._workflow_rename_stage(stage_id, name, revision)
        return self.stage_catalogue(model)

    def _record_target(self, model, record_id):
        """The record a position belongs to, read as the caller."""
        self._staff()
        if model == RUN:
            return self._run(record_id)
        return self._source(model, record_id)

    @api.model
    def move_record_stage(self, model, record_id, stage_id):
        """A person moves a record into a user-made stage that waits for them."""
        record = self._record_target(model, record_id)
        stage = self.env['pb.workflow.stage'].sudo().browse(int(stage_id or 0)).exists()
        if not stage or not stage.active or stage.company_id != self.env.company:
            raise AccessError(_('This stage is not available in your current company.'))
        company = stage.company_id
        if model == RUN:
            if not stage.workflow_id or stage.workflow_id != record.sudo().workflow_id:
                raise UserError(_('This stage belongs to another process.'))
            source, waiting = record, record.sudo()
        else:
            if stage.source_model != model:
                raise UserError(_('This stage belongs to another kind of record.'))
            source = record
            waiting = self.env[RUN].sudo().search([('company_id', '=', company.id), ('source_model', '=', model),
                                                   ('source_id', '=', record.id), ('state', 'in', ['running', 'waiting'])])
        if stage.enter != 'person':
            raise UserError(_('Records get into “%s” by themselves. Nobody needs to move them.', stage.name))
        if model != RUN:
            contract = self._contract(model, source)
            status = self._status_value(contract, source)
            if str(status) != str(stage.anchor_value):
                anchor = next((s['name'] for s in contract['stages'] if str(s['key']) == stage.anchor_value), '')
                raise UserError(_('This is not at %(anchor)s, so it cannot move to %(stage)s yet.', anchor=anchor, stage=stage.name))
        if not self._can_design():
            # The caller must be who the stage names, resolved the way a task
            # owner is: through a run on this record when there is one (so
            # "the person who started it" works), else from the record.
            owner = stage.enter_owner or {}
            service = system(self.env, company)['pb.workflow.studio']
            allowed = False
            for run in waiting:
                try:
                    allowed = allowed or service._resolve_owner(service.env[RUN].browse(run.id), owner) == self.env.uid
                except (AccessError, UserError):
                    continue
            if not allowed and model != RUN and owner.get('kind') != 'initiator':
                try:
                    allowed = service._resolve_owner_on(service.env[model].browse(source.id), company, owner) == self.env.uid
                except (AccessError, UserError):
                    allowed = False
            if not allowed:
                raise AccessError(_('Only %(who)s can move this to %(stage)s.',
                                    who=self._owner_words(stage.source_model, stage.enter_owner), stage=stage.name))
        target_model = RUN if model == RUN else model
        self._set_position(target_model, record.id, stage, company,
                           run=waiting[:1] if waiting else None, mover=self.env.user)
        for run in waiting:
            if run.state in ('running', 'waiting'):
                run._advance()
        return self.record_stage(model, record.id)

    @api.model
    def record_stage(self, model, record_id):
        """Where a record is, by module status and user-made stage.

        `done` is said only of stages before the current one, and for a
        user-made stage only when history shows the record really entered
        it; a stage the record went past without entering is `passed`."""
        record = self._record_target(model, record_id)
        company = record.sudo().company_id
        if model == RUN:
            contract = self._contract('')
            stages = self._user_stages('', record.sudo().workflow_id, company)
            status, runs = None, record.sudo()
        else:
            contract = self._contract(model, record)
            stages = self._user_stages(model, self.env['pb.workflow'], company)
            status = self._status_value(contract, record)
            runs = self.env[RUN].sudo().search([('company_id', '=', company.id), ('source_model', '=', model),
                                                ('source_id', '=', record.id)])
        position = self._record_position(model, record.id, company)
        entered = set(self.env['pb.workflow.log'].sudo().search([
            ('run_id', 'in', runs.ids), ('stage_id', '!=', False)]).mapped('stage_id').ids) if runs else set()
        merged = self._merged(contract, stages)
        exits = [{'key': c['key'], 'name': c['name'], 'here': str(c['key']) == str(status)}
                 for kind, c in merged if kind == 'core' and c.get('exit')]
        track = [(kind, item) for kind, item in merged if not (kind == 'core' and item.get('exit'))]
        if position:
            here = next((i for i, (k, s) in enumerate(track) if k == 'yours' and s == position.stage_id), None)
        else:
            here = next((i for i, (k, s) in enumerate(track) if k == 'core' and str(s['key']) == str(status)), None)
        stopped = any(e['here'] for e in exits)
        rows = []
        for i, (kind, item) in enumerate(track):
            if stopped:
                state = 'stopped'
            elif here is None or i > here:
                state = 'later'
            elif i == here:
                state = 'here'
            elif kind == 'yours':
                state = 'done' if item.id in entered else 'passed'
            else:
                state = 'passed' if item.get('optional') else 'done'
            row = {'kind': kind, 'state': state}
            if kind == 'core':
                row.update(key=item['key'], name=item['name'], approval=bool(item.get('approval')))
            else:
                anchor = next((c['name'] for c in contract['stages'] if str(c['key']) == str(item.anchor_value)), '')
                row.update(key=item.id, name=item.name, counts_as=anchor)
            rows.append(row)
        current = None
        if position:
            current = {'kind': 'yours', 'key': position.stage_id.id, 'name': position.stage_id.name,
                       'since': str(position.entered_at), 'by': position.entered_by.name or ''}
        elif status is not None:
            core = next((c for c in contract['stages'] if str(c['key']) == str(status)), None)
            if core:
                current = {'kind': 'core', 'key': core['key'], 'name': core['name'], 'exit': bool(core.get('exit'))}
        approval = next((c['key'] for c in contract['stages'] if c.get('approval')), None)
        return {'model': model, 'record_id': record.id, 'source': contract['source'],
                'area': contract['area'], 'track': rows, 'exits': exits, 'current': current,
                'approval_at': approval}

    def _record_stage_safe(self, model, record_id):
        try:
            return self.record_stage(model, record_id)
        except (AccessError, UserError):
            return None
